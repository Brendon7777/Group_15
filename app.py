"""
LTSM Portal – Flask application (Task 3A).

Serves the Jinja templates in Templates/ and the JSON API under /api that the
fetch() code in static/js/ calls. See README.md for the endpoint inventory.

Run:  python app.py   then open http://127.0.0.1:5000
"""
import math
import os
import re
import smtplib
import ssl
from collections import Counter
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, session
import db
import model
import inventory_model_live
from blueprints import (
    BLUEPRINTS,
    auth_bp,
    bookings_bp,
    catalog_bp,
    circulation_bp,
    dashboard_bp,
    evidence_bp,
    health_bp,
    inventory_bp,
    maintenance_bp,
    notifications_bp,
    pages_bp,
    reports_bp,
    requests_bp,
)
from config import config_for_environment

try:  # optional: load settings from a local .env file (see .env.example)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()

app = Flask(__name__, template_folder="Templates", static_folder="static")
app.config.from_object(config_for_environment(APP_ENV))
APP_TIMEZONE = app.config["APP_TIMEZONE"]
db.init_app(app)

def now():
    """Current time in the school's timezone (servers usually run in UTC, which is 2 hours behind South Africa)."""
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def today():
    return now().date()


CATEGORIES = ["Textbooks", "Stationery", "Consumables", "Equipment", "Other"]
FOUNDATION_PHASE_GRADES = ("Grade 1", "Grade 2", "Grade 3")
CATEGORY_WORD = {"Textbooks": "textbook", "Stationery": "stationery", "Consumables": "consumable", "Equipment": "equipment", "Other": "other"}
REQUEST_TONES = {"In review": "warning", "Approved": "ok", "Ready for collection": "blue", "Fulfilled": "ok", "Declined": "danger"}
BOOKING_TONES = {"Confirmed": "ok", "Awaiting approval": "warning", "Declined": "danger"}
MAINTENANCE_TONES = {"Open": "warning", "In repair": "warning", "Out of service": "danger", "Resolved": "ok"}
EVIDENCE_METRICS = (
    {"key": "request_waiting", "label": "Wait for collection readiness", "unit": "minutes", "direction": "lower", "sample": "requests made ready", "help": "Average time from request submission until it is ready."},
    {"key": "collection_waiting", "label": "Time from ready to collection", "unit": "minutes", "direction": "lower", "sample": "requests collected", "help": "Average time from ready status until the item is issued."},
    {"key": "request_fulfillment", "label": "Request to fulfillment", "unit": "minutes", "direction": "lower", "sample": "requests fulfilled", "help": "Average time from request submission until the item is issued."},
    {"key": "unnecessary_trips", "label": "Unnecessary trips", "unit": "per 100 requests", "direction": "lower", "sample": "requests", "manual": True, "help": "Trips caused by an avoidable visit, per 100 requests."},
    {"key": "follow_up_enquiries", "label": "Follow-up enquiries", "unit": "per 100 requests", "direction": "lower", "sample": "requests", "manual": True, "help": "Extra status enquiries, per 100 requests."},
    {"key": "inventory_accuracy", "label": "Inventory count accuracy", "unit": "percent", "direction": "higher", "sample": "physical counts", "manual": True, "help": "Percentage of physical counts that match the recorded quantity."},
    {"key": "potential_excess_stock", "label": "Potential excess consumable stock", "unit": "R", "direction": "lower", "sample": "forecasted, priced consumables assessed", "snapshot": True, "help": "Current value of consumables above the live forecast target; a potential excess-stock indicator, not confirmed waste."},
    {"key": "booking_conflicts", "label": "Booking conflict rate", "unit": "percent", "direction": "lower", "sample": "booking attempts", "help": "Percentage of booking attempts blocked by another booking."},
    {"key": "report_preparation", "label": "Report preparation time", "unit": "minutes", "direction": "lower", "sample": "reports", "manual": True, "help": "Average minutes spent preparing a report."},
    {"key": "motion_time", "label": "Searching and moving inventory time", "unit": "minutes", "direction": "lower", "sample": "motion events", "manual": True, "help": "Total staff minutes spent searching for or moving inventory items."},
    {"key": "incorrect_fulfillment", "label": "Fulfillment correction incidents", "unit": "per 100 fulfilled requests", "direction": "lower", "sample": "requests fulfilled", "manual": True, "help": "Staff-recorded item or quantity corrections per 100 fulfilled requests. A request can have more than one correction."},
    {"key": "equipment_downtime", "label": "Equipment downtime", "unit": "hours", "direction": "lower", "sample": "outages", "manual": True, "help": "Total hours equipment was recorded out of service."},
)
AUTOMATIC_EVIDENCE_METRICS = (
    {"key": "requests_submitted", "label": "Requests submitted", "unit": "requests", "kind": "count"},
    {"key": "request_waiting", "label": "Average time to ready", "unit": "minutes", "kind": "duration", "direction": "lower"},
    {"key": "collection_waiting", "label": "Average time from ready to collection", "unit": "minutes", "kind": "duration", "direction": "lower"},
    {"key": "request_fulfillment", "label": "Average request-to-fulfillment time", "unit": "minutes", "kind": "duration", "direction": "lower"},
    {"key": "bookings_requested", "label": "Bookings submitted", "unit": "bookings", "kind": "count"},
    {"key": "booking_conflicts", "label": "Booking conflict rate", "unit": "percent", "kind": "rate", "direction": "lower"},
)
MANUAL_EVIDENCE_KEYS = tuple(
    metric["key"] for metric in EVIDENCE_METRICS if metric.get("manual")
)


# --------------------------------------------------------------------------- #
# Errors, validation and sign-in checks
# --------------------------------------------------------------------------- #
class ApiError(Exception):
    def __init__(self, message, status=400, fields=None):
        super().__init__(message)
        self.message, self.status, self.fields = message, status, fields or {}


@app.errorhandler(ApiError)
def handle_api_error(error):
    return jsonify(error=error.message, fields=error.fields), error.status


@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith("/api/"):
        return jsonify(error="That endpoint does not exist."), 404
    return error


@app.errorhandler(405)
def handle_method_not_allowed(error):
    if request.path.startswith("/api/"):
        return jsonify(error="That method is not allowed here."), 405
    return error


@app.after_request
def no_cache_for_api(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class Validator:
    """Collects one message per bad field, then raises a single 400 with all of them."""

    def __init__(self, data):
        self.data, self.errors = data, {}

    def _fail(self, key, message):
        self.errors.setdefault(key, message)

    def text(self, key, label, min_len=1, max_len=100):
        value = self.data.get(key)
        value = value.strip() if isinstance(value, str) else ""
        if not min_len <= len(value) <= max_len:
            self._fail(key, f"{label} is required (up to {max_len} characters)." if min_len == 1 else f"{label} must be {min_len}–{max_len} characters.")
        return value

    def integer(self, key, label, low, high):
        value = self.data.get(key)
        if isinstance(value, str) and value.strip().isdigit():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            self._fail(key, f"{label} must be a whole number between {low} and {high}.")
            return None
        return value

    def decimal(self, key, label, low, high):
        value = self.data.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = None
        if number is None or not math.isfinite(number) or not low <= number <= high:
            self._fail(key, f"{label} must be a number between {low} and {high}.")
            return None
        return number

    def choice(self, key, label, options):
        value = self.data.get(key)
        if value not in options:
            self._fail(key, f"Choose a valid {label.lower()}.")
        return value

    def email(self, key, label):
        value = self.text(key, label, 3, 100)
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            self._fail(key, f"Enter a valid {label.lower()}.")
        return value.lower()

    def day(self, key, label, not_before=None, not_after=None):
        try:
            value = datetime.strptime(str(self.data.get(key)), "%Y-%m-%d").date()
        except ValueError:
            self._fail(key, f"{label} must be a valid date.")
            return None
        if not_before and value < not_before:
            self._fail(key, f"{label} cannot be before {not_before.isoformat()}.")
        if not_after and value > not_after:
            self._fail(key, f"{label} cannot be after {not_after.isoformat()}.")
        return value

    def clock(self, key, label):
        try:
            return datetime.strptime(str(self.data.get(key)), "%H:%M").strftime("%H:%M")
        except ValueError:
            self._fail(key, f"{label} must be a valid time.")
            return None

    def done(self):
        if self.errors:
            raise ApiError(" ".join(self.errors.values()), 400, self.errors)


def json_body():
    if not request.is_json:  # also blocks cross-site HTML form posts
        raise ApiError("Send the request as JSON.", 415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("The request body must be a JSON object.", 400)
    return data


def current_user():
    user_id = session.get("uid")
    user = model.get_user_by_id(user_id) if user_id is not None else None
    if user is None or user["role"] not in ("teacher", "ltsm"):
        session.pop("uid", None)
        return None
    return user


def api_route(*roles):
    """Require a signed-in user (optionally one of `roles`); the view receives the user first."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                raise ApiError("Please sign in to continue.", 401)
            if roles and user["role"] not in roles:
                raise ApiError("You do not have permission to do that.", 403)
            return view(user, *args, **kwargs)
        return wrapper
    return decorator


def resource_rows():
    return db.query_all(
        """
        SELECT resource_id AS id, resource_name AS name,
               COALESCE(description, '') AS description, category, inventory_type, grade,
               unit_price, quantity_in_stock AS on_hand,
               CAST(quantity_in_stock - COALESCE((
                   SELECT SUM(rr.allocated_quantity)
                   FROM resource_request AS rr
                   WHERE rr.resource_id = resource.resource_id
                     AND rr.status = 'Ready for collection'
               ), 0) AS SIGNED) AS stock,
               CAST(COALESCE((
                   SELECT SUM(rr.allocated_quantity)
                   FROM resource_request AS rr
                   WHERE rr.resource_id = resource.resource_id
                     AND rr.status = 'Ready for collection'
               ), 0) AS SIGNED) AS reserved,
               reorder_level,
               unit_of_measure AS unit, COALESCE(storage_location, '') AS storage_location
        FROM resource
        ORDER BY resource_name, grade, resource_id
        """
    )


def date_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def datetime_value(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return str(value)


def time_value(value):
    return value.strftime("%H:%M") if hasattr(value, "strftime") else str(value)[:5]


def matches(item, query, category):
    haystack = f"{item['name']} {item['description']} {item['category']}".lower()
    return query.lower() in haystack and (not category or item["category"] == category)


def is_foundation_phase_grade(value):
    match = re.fullmatch(r"(?:grade\s*)?(\d+)", str(value or "").strip(), re.IGNORECASE)
    return bool(match and int(match.group(1)) in (1, 2, 3))


def grade_number_in_name(name):
    match = re.search(r"\bgrade\s*(\d+)\b", name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def resource_in_foundation_scope(category, grade):
    return category != "Textbooks" or is_foundation_phase_grade(grade)


def availability(item):
    if item["stock"] == 0:
        return "Out of stock", "danger"
    if item["category"] == "Equipment":
        return "Bookable", "warning"
    if item["stock"] <= item["reorder_level"]:
        return "Limited", "warning"
    return "Available", "ok"


def stock_status(item):
    if item["stock"] == 0:
        return "Out of stock", "danger"
    if item["stock"] <= item["reorder_level"] / 2:
        return "Low stock", "danger"
    if item["stock"] < item["reorder_level"]:
        return "Low stock", "warning"
    return "In stock", "ok"


# --------------------------------------------------------------------------- #
# Pages (the templates link to each other as login.html, my-requests.html, ...)
# --------------------------------------------------------------------------- #
PUBLIC_PAGES = {"index", "login", "register", "suggest-resource"}
USER_PAGES = {"user-dashboard", "view-resources", "resource", "request-resources", "my-requests", "book-equipment"}
COMMITTEE_PAGES = {"ltsm-dashboard", "manage-inventory", "request-management", "manage-bookings", "issue-return", "maintenance", "reports", "manage-users", "inventory-summary"}


def dashboard_for(user):
    return "/ltsm-dashboard.html" if user["role"] == "ltsm" else "/user-dashboard.html"


@pages_bp.get("/")
def home():
    return render_template("index.html")


@pages_bp.get("/login")
def login():
    return render_template("login.html")


@pages_bp.get("/register")
def register():
    return render_template("register.html")


@pages_bp.get("/<page>.html")
def page(page):
    if page not in PUBLIC_PAGES | USER_PAGES | COMMITTEE_PAGES:
        return render_template("index.html"), 404
    if page == "resource":
        page = "view-resources"
    if page in PUBLIC_PAGES:
        if page == "suggest-resource":
            return render_template(f"{page}.html", user=current_user())
        return render_template(f"{page}.html")
    user = current_user()
    if user is None:
        return redirect("/login")
    if page in COMMITTEE_PAGES and user["role"] != "ltsm":
        return redirect(dashboard_for(user))
    if page == "inventory-summary":
        summary_warnings = []
        try:
            results = inventory_model_live.calculate_from_database(
                db.get_db(), warnings=summary_warnings
            )
        except Exception:
            app.logger.exception("Could not calculate the live inventory summary")
            return render_template(
                "inventory_summary.html",
                user=user,
                load_error="The inventory summary could not be calculated from the database. Please check the resource and demand-history records.",
            ), 503
        by_policy = {
            policy: sorted(
                (result for result in results.values() if result["policy"] == policy),
                key=lambda result: result["resource_id"],
            )
            for policy in inventory_model_live.policies
        }
        return render_template(
            "inventory_summary.html",
            user=user,
            results=by_policy,
            policies=inventory_model_live.policies,
            service_level=inventory_model_live.service_level,
            summary_warnings=summary_warnings,
        )
    return render_template(f"{page}.html", user=user)


NOTIFICATION_MODULES = ("request-management", "my-requests", "bookings")
NOTIFICATION_PAGE_SIZE = 20


def create_notification(cursor, user_id, module, title, message, target_url):
    cursor.execute(
        """
        INSERT INTO user_notification
          (user_id, module, title, message, target_url)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, module, title, message, target_url),
    )


def send_email(to_email, subject, body):
    """Send a plain-text email. Missing SMTP configuration disables delivery, not the app."""
    if not to_email:
        return False

    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        app.logger.warning("Email not sent: SMTP_HOST is not configured.")
        return False

    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        app.logger.error("Email not sent: SMTP_PORT must be a whole number.")
        return False
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    from_email = os.environ.get("SMTP_FROM", username).strip()
    from_name = os.environ.get("SMTP_FROM_NAME", "LTSM Portal").strip()
    use_ssl = os.environ.get("SMTP_USE_SSL", "false").strip().lower() in ("1", "true", "yes")
    use_tls = os.environ.get("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes")

    if not from_email:
        app.logger.warning("Email not sent: SMTP_FROM or SMTP_USERNAME must be configured.")
        return False

    message = EmailMessage()
    message["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
                if username:
                    smtp.login(username, password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                if use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                if username:
                    smtp.login(username, password)
                smtp.send_message(message)
        app.logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except (smtplib.SMTPException, OSError, ssl.SSLError, ValueError) as error:
        app.logger.error("Email delivery failed for %s: %s", to_email, error)
        return False


def notify_role(cursor, role, module, title, message, target_url):
    cursor.execute(
        "SELECT user_id FROM users WHERE role = %s AND is_active = TRUE",
        (role,),
    )
    for recipient in cursor.fetchall():
        create_notification(
            cursor, recipient["user_id"], module, title, message, target_url
        )


@notifications_bp.get("/api/notifications")
@api_route()
def api_notifications(user):
    module = request.args.get("module", "").strip()
    if module and module not in NOTIFICATION_MODULES:
        raise ApiError("Choose a valid notification module.")
    before_id = request.args.get("before_id", "").strip()
    if before_id:
        try:
            before_id = int(before_id)
        except ValueError as error:
            raise ApiError("Notification cursor must be a positive ID.") from error
        if before_id < 1:
            raise ApiError("Notification cursor must be a positive ID.")
    else:
        before_id = None

    counts = db.query_all(
        """
        SELECT module, COUNT(*) AS unread_count
        FROM user_notification
        WHERE user_id = %s AND read_at IS NULL
        GROUP BY module
        """,
        (user["id"],),
    )
    items = []
    has_more = False
    if module:
        query = """
            SELECT notification_id AS id, module, title, message, target_url,
                   DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at,
                   (read_at IS NULL) AS unread, (done_at IS NOT NULL) AS done
            FROM user_notification
            WHERE user_id = %s AND module = %s
        """
        parameters = (user["id"], module)
        if before_id is not None:
            query += " AND notification_id < %s"
            parameters += (before_id,)
        query += """
            ORDER BY created_at DESC, notification_id DESC
            LIMIT %s
        """
        rows = db.query_all(query, parameters + (NOTIFICATION_PAGE_SIZE + 1,))
        has_more = len(rows) > NOTIFICATION_PAGE_SIZE
        items = rows[:NOTIFICATION_PAGE_SIZE]
    return jsonify(
        unread={item["module"]: item["unread_count"] for item in counts},
        items=items,
        has_more=has_more,
        next_before_id=items[-1]["id"] if has_more else None,
    )


@notifications_bp.post("/api/notifications/read")
@api_route()
def api_mark_notifications_read(user):
    v = Validator(json_body())
    module = v.choice("module", "Module", NOTIFICATION_MODULES)
    v.done()
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_notification
                SET read_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND module = %s AND read_at IS NULL
                """,
                (user["id"], module),
            )
            changed = cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message="Notifications marked as read.", updated=changed)


@notifications_bp.post("/api/notifications/<int:notification_id>/done")
@api_route()
def api_mark_notification_done(user, notification_id):
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_notification
                SET done_at = CURRENT_TIMESTAMP,
                    read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
                WHERE notification_id = %s AND user_id = %s AND done_at IS NULL
                """,
                (notification_id, user["id"]),
            )
            changed = cursor.rowcount
            if not changed:
                cursor.execute(
                    """
                    SELECT notification_id
                    FROM user_notification
                    WHERE notification_id = %s AND user_id = %s
                    """,
                    (notification_id, user["id"]),
                )
                if cursor.fetchone() is None:
                    raise ApiError("That notification does not exist.", 404)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message="Notification marked as done.", done=True, updated=changed)


# --------------------------------------------------------------------------- #
# API: accounts
# --------------------------------------------------------------------------- #
@auth_bp.post("/api/login")
def api_login():
    data = json_body()
    username = str(data.get("username", "")).strip().lower()
    requested_role = data.get("role")
    user = (
        model.authenticate_user(username, str(data.get("password", "")), requested_role)
        if requested_role in ("teacher", "ltsm")
        else None
    )
    if user is None:
        raise ApiError("Incorrect role, username or password.", 401)  # one message so accounts cannot be probed
    session.clear()
    session["uid"] = user["id"]
    return jsonify(user={"id": user["id"], "name": user["name"], "role": user["role"]}, redirect=dashboard_for(user))


@auth_bp.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(redirect="/login")


@auth_bp.post("/api/register")
def api_register():
    data = json_body()
    v = Validator(data)
    name = v.text("full_name", "Full name", 2, 100)
    role = v.choice("account_type", "Account type", ("teacher",))
    school_id = v.text("school_id", "Staff number", 1, 40)
    email = v.email("email", "Email address")
    password = data.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        v._fail("password", "Password must be 8–128 characters.")
    elif data.get("confirm_password") != password:
        v._fail("confirm_password", "Passwords do not match.")
    v.done()
    try:
        model.create_user(name, school_id, email, password, role, account_status="pending")
    except model.UserAlreadyExistsError as error:
        field = error.field
        label = "email address" if field == "email" else "staff number"
        raise ApiError(
            f"An account with that {label} already exists.",
            409,
            {field: "Already registered."},
        ) from error
    return jsonify(
        message=(
            "Account request submitted. An LTSM committee member must approve it "
            "before you can sign in."
        )
    ), 201


@auth_bp.get("/api/committee/users")
@api_route("ltsm")
def api_committee_users(user):
    users = model.list_users()
    return jsonify(items=[
        {
            "id": row["user_id"],
            "name": row["full_name"],
            "school_id": row["school_id"],
            "email": row["email"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "account_status": row["account_status"],
            "is_current_user": row["user_id"] == user["id"],
        }
        for row in users
    ])


@auth_bp.post("/api/committee/users/<int:user_id>/approve")
@api_route("ltsm")
def api_committee_approve_user(user, user_id):
    try:
        approved = model.approve_user_account(user_id)
    except model.UserManagementError as error:
        raise ApiError(str(error), 409, {"user_id": error.code}) from error
    if not approved:
        raise ApiError("That account request does not exist.", 404)
    return jsonify(message="Account approved. The user can now sign in.")


@auth_bp.post("/api/committee/users")
@api_route("ltsm")
def api_committee_create_user(user):
    data = json_body()
    validator = Validator(data)
    name = validator.text("full_name", "Full name", 2, 100)
    role = validator.choice("role", "Role", ("staff", "ltsm"))
    school_id = validator.text("school_id", "Staff / committee ID", 1, 40)
    email = validator.email("email", "Email address")
    password = data.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        validator._fail("password", "Password must be 8–128 characters.")
    validator.done()
    try:
        new_user_id = model.create_user(name, school_id, email, password, role)
    except model.UserAlreadyExistsError as error:
        field = error.field
        label = "email address" if field == "email" else "staff / committee ID"
        raise ApiError(
            f"An account with that {label} already exists.",
            409,
            {field: "Already registered."},
        ) from error
    return jsonify(message="User account created.", id=new_user_id), 201


@auth_bp.post("/api/committee/users/<int:user_id>/status")
@api_route("ltsm")
def api_committee_set_user_status(user, user_id):
    data = json_body()
    active = data.get("is_active")
    if not isinstance(active, bool):
        raise ApiError("Account status must be true or false.", 400, {"is_active": "Choose a valid status."})
    try:
        updated = model.set_user_active(user_id, active, user["id"])
    except model.UserManagementError as error:
        raise ApiError(str(error), 409, {"user_id": error.code}) from error
    if not updated:
        raise ApiError("That user account does not exist.", 404)
    return jsonify(message="User account reactivated." if active else "User account deactivated.")


# --------------------------------------------------------------------------- #
# API: teacher / staff features
# --------------------------------------------------------------------------- #
@catalog_bp.get("/api/resources")
@api_route()
def api_resources(user):
    query, category = request.args.get("q", "").strip(), request.args.get("category", "").strip()
    items = []
    for item in resource_rows():
        if not resource_in_foundation_scope(item["category"], item["grade"]):
            continue
        if not matches(item, query, category):
            continue
        label, tone = availability(item)
        items.append({**{k: item[k] for k in ("id", "name", "description", "category", "grade", "stock", "unit")}, "availability": label, "tone": tone})
    return jsonify(items=items)


@catalog_bp.post("/api/suggestions")
def api_create_suggestion():
    data = json_body()
    v = Validator(data)
    row = {
        "name": v.text("resource_name", "Resource name", 1, 100),
        "message": v.text("message", "Suggestion", 10, 500),
    }
    anonymous = data.get("anonymous", True)
    if not isinstance(anonymous, bool):
        raise ApiError("Choose whether to submit anonymously.", 400, {"anonymous": "Choose a valid option."})
    user = current_user()
    submitter_name = None
    user_id = None
    if not anonymous:
        if user:
            user_id = user["id"]
        else:
            submitter_name = v.text("submitter_name", "Your name", 1, 100)
    v.done()
    suggestion_id = db.execute(
        """
        INSERT INTO resource_suggestion
          (user_id, submitter_name, resource_name, message)
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, submitter_name, row["name"], row["message"]),
    )
    return jsonify(message="Thank you. Your suggestion has been sent to the LTSM committee.", id=suggestion_id), 201


@requests_bp.post("/api/requests")
@api_route()
def api_create_request(user):
    v = Validator(json_body())
    row = {
        "user_id": user["id"],
        "name": v.text("resource_name", "Resource name", 1, 100),
        "category": v.choice("category", "Category", CATEGORIES),
        "quantity": v.integer("quantity", "Quantity", 1, 100),
        "needed_by": v.day("needed_by", "Needed by", not_before=today()),
        "purpose": v.text("purpose", "Reason for request", 10, 500),
    }
    v.done()
    inventory_item = db.query_one(
        """
        SELECT r.resource_id, r.resource_name AS name, r.category,
               r.grade,
               CAST(r.quantity_in_stock - COALESCE((
                   SELECT SUM(rr.allocated_quantity)
                   FROM resource_request AS rr
                   WHERE rr.resource_id = r.resource_id
                     AND rr.status = 'Ready for collection'
               ), 0) AS SIGNED) AS stock,
               r.unit_of_measure AS unit
        FROM resource AS r
        WHERE LOWER(TRIM(r.resource_name)) = LOWER(TRIM(%s))
        ORDER BY r.grade, r.resource_id
        LIMIT 1
        """,
        (row["name"],),
    )
    if inventory_item and not resource_in_foundation_scope(
        inventory_item["category"], inventory_item["grade"]
    ):
        raise ApiError(
            "Only Grade 1, Grade 2, and Grade 3 books can be requested.",
            400,
            {"resource_name": "Choose a Grade 1, 2, or 3 book."},
        )
    requested_grade = grade_number_in_name(row["name"])
    is_book_request = row["category"] == "Textbooks" or bool(
        re.search(r"\b(?:book|textbook|workbook)\b", row["name"], re.IGNORECASE)
    )
    if is_book_request and requested_grade not in (None, 1, 2, 3):
        raise ApiError(
            "Only Grade 1, Grade 2, and Grade 3 books can be requested.",
            400,
            {"resource_name": "Choose a Grade 1, 2, or 3 book."},
        )
    if not inventory_item and is_book_request and requested_grade not in (1, 2, 3):
        raise ApiError(
            "Book requests must be for Grade 1, Grade 2, or Grade 3.",
            400,
            {"resource_name": "Include Grade 1, Grade 2, or Grade 3 in the book name."},
        )
    if inventory_item:
        if row["quantity"] > inventory_item["stock"]:
            raise ApiError(
                f"Only {inventory_item['stock']} {inventory_item['unit']} of {inventory_item['name']} are currently available.",
                409,
                {"quantity": "Requested quantity exceeds current availability."},
            )
        row["category"] = inventory_item["category"]
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO resource_request
                  (user_id, resource_id, resource_name, category, quantity, needed_by, purpose,
                   submitted_date, submitted_at, status, latest_update)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'In review', 'Committee review in progress')
                """,
                (
                    user["id"], inventory_item["resource_id"] if inventory_item else None,
                    row["name"], row["category"], row["quantity"],
                    row["needed_by"], row["purpose"], today(), now().replace(tzinfo=None),
                ),
            )
            request_id = cursor.lastrowid
            notify_role(
                cursor, "ltsm", "request-management", "New resource request",
                f"{user['name']} requested {row['quantity']} × {row['name']}.",
                "/request-management.html",
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message="Request submitted.", id=request_id), 201


@requests_bp.get("/api/requests")
@api_route()
def api_my_requests(user):
    status = request.args.get("status", "").strip()
    sql = """
        SELECT request_id AS id, resource_name AS name, category,
               submitted_date AS submitted, quantity, allocated_quantity,
               collection_slot, cl.location_name AS collection_location,
               needed_by, status,
               latest_update AS `update`
        FROM resource_request
        LEFT JOIN collection_location AS cl
          ON cl.location_id = resource_request.collection_location_id
        WHERE user_id = %s
    """
    params = [user["id"]]
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY submitted_date DESC, request_id DESC"
    rows = db.query_all(sql, params)
    return jsonify(items=[
        {
            **row,
            "submitted": date_value(row["submitted"]),
            "needed_by": date_value(row["needed_by"]) if row["needed_by"] else None,
            "collection_slot": (
                row["collection_slot"].isoformat(sep=" ", timespec="minutes")
                if row["collection_slot"] else None
            ),
            "tone": REQUEST_TONES[row["status"]],
        }
        for row in rows
    ])


@catalog_bp.get("/api/equipment")
@api_route()
def api_equipment(user):
    return jsonify(items=[
        {
            "id": item["id"], "name": item["name"], "stock": item["stock"],
            "storage_location": item["storage_location"],
        }
        for item in resource_rows()
        if item["category"] == "Equipment"
    ])


@bookings_bp.post("/api/bookings")
@api_route()
def api_create_booking(user):
    v = Validator(json_body())
    equipment_id = v.integer("equipment_id", "Equipment", 1, 10**9)
    day = v.day("booking_date", "Date", not_before=today())
    start, end = v.clock("start_time", "Start time"), v.clock("end_time", "End time")
    room = v.text("room", "Room / location", 1, 80)
    purpose = v.text("purpose", "Purpose", 1, 160)
    if start and end and end <= start:
        v._fail("end_time", "End time must be after start time.")
    v.done()
    booking_start = datetime.combine(day, datetime.strptime(start, "%H:%M").time())
    booking_end = datetime.combine(day, datetime.strptime(end, "%H:%M").time())
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT resource_id AS id, resource_name AS name, category,
                       quantity_in_stock AS stock
                FROM resource WHERE resource_id = %s FOR UPDATE
                """,
                (equipment_id,),
            )
            item = cursor.fetchone()
            if not item or item["category"] != "Equipment":
                raise ApiError("Choose equipment from the list.", 400, {"equipment_id": "Unknown equipment."})
            cursor.execute(
                """
                SELECT COUNT(*) AS booking_count
                FROM equipment_booking
                WHERE resource_id = %s
                  AND booking_date BETWEEN DATE_SUB(%s, INTERVAL 1 DAY)
                                       AND DATE_ADD(%s, INTERVAL 1 DAY)
                  AND status != 'Declined'
                  AND TIMESTAMP(booking_date, start_time)
                      < DATE_ADD(%s, INTERVAL 20 MINUTE)
                  AND DATE_ADD(TIMESTAMP(booking_date, end_time), INTERVAL 20 MINUTE) > %s
                """,
                (item["id"], day, day, booking_end, booking_start),
            )
            overlapping = cursor.fetchone()["booking_count"]
            if overlapping >= item["stock"]:
                if overlapping:
                    cursor.execute(
                        """
                        INSERT INTO operational_measurement
                          (metric_key, occurred_at, resource_id, notes, recorded_by_user_id)
                        VALUES ('booking_conflict', %s, %s, %s, %s)
                        """,
                        (
                            now().replace(tzinfo=None),
                            item["id"],
                            f"Booking attempt for {day.isoformat()} {start}–{end} blocked by an existing booking.",
                            user["id"],
                        ),
                    )
                    connection.commit()
                raise ApiError(f"No {item['name']} is free on {day.isoformat()} between {start} and {end}. Try another time.", 409)
            cursor.execute(
                """
                INSERT INTO equipment_booking
                  (user_id, resource_id, booking_date, start_time, end_time,
                   requested_at, room, purpose, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Awaiting approval')
                """,
                (
                    user["id"], item["id"], day, start, end,
                    now().replace(tzinfo=None), room, purpose,
                ),
            )
            booking_id = cursor.lastrowid
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message=f"Booking requested: {item['name']} on {day.isoformat()}, {start}–{end}. The LTSM committee will confirm it."), 201


@bookings_bp.get("/api/bookings")
@api_route()
def api_my_bookings(user):
    rows = db.query_all(
        """
        SELECT b.booking_id AS id, r.resource_name AS equipment,
               b.booking_date AS `date`, b.start_time AS `start`, b.end_time AS `end`,
               b.room, b.purpose, b.status
        FROM equipment_booking AS b
        JOIN resource AS r ON r.resource_id = b.resource_id
        WHERE b.user_id = %s AND b.booking_date >= %s
        ORDER BY b.booking_date, b.start_time, b.booking_id
        """,
        (user["id"], today()),
    )
    return jsonify(items=[
        {
            **booking,
            "date": date_value(booking["date"]),
            "start": time_value(booking["start"]),
            "end": time_value(booking["end"]),
            "tone": BOOKING_TONES[booking["status"]],
        }
        for booking in rows
    ])


# --------------------------------------------------------------------------- #
# API: LTSM committee features
# --------------------------------------------------------------------------- #
@inventory_bp.get("/api/inventory")
@api_route("ltsm")
def api_inventory(user):
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    inventory_type = request.args.get("type", "").strip()
    items = []
    for item in filter(
        lambda i: resource_in_foundation_scope(i["category"], i["grade"])
        and matches(i, query, category)
        and (not inventory_type or i["inventory_type"] == inventory_type),
        resource_rows(),
    ):
        label, tone = stock_status(item)
        items.append({
            **{k: item[k] for k in ("id", "name", "category", "inventory_type", "grade", "stock", "reorder_level", "description", "unit", "storage_location")},
            "unit_price": float(item["unit_price"]) if item["unit_price"] is not None else None,
            "status": label,
            "tone": tone,
        })
    return jsonify(items=items)


@inventory_bp.post("/api/inventory")
@api_route("ltsm")
def api_add_inventory(user):
    v = Validator(json_body())
    name = v.text("item_name", "Item name", 1, 100)
    category = v.choice("category", "Category", CATEGORIES)
    grade = v.choice("grade", "Grade", FOUNDATION_PHASE_GRADES) if category == "Textbooks" else None
    inventory_type = v.choice("inventory_type", "Inventory type", ("consumable", "non_consumable"))
    stock = v.integer("quantity", "Quantity", 0, 10000)
    reorder = v.integer("reorder_level", "Reorder level", 0, 10000)
    description = v.text("description", "Description", 0, 255)
    unit = v.text("unit", "Unit", 0, 45) or "units"
    storage_location = v.text("storage_location", "Storage location", 0, 120)
    raw_unit_price = v.data.get("unit_price")
    unit_price = (
        None if raw_unit_price in (None, "")
        else v.decimal("unit_price", "Unit price", 0, 99999999.99)
    )
    v.done()
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT resource_id FROM resource WHERE LOWER(resource_name) = LOWER(%s) LIMIT 1",
                (name,),
            )
            if cursor.fetchone():
                raise ApiError(f"{name} is already in the inventory.", 409, {"item_name": "Already exists."})
            cursor.execute(
                """
                INSERT INTO resource
                  (resource_name, category, inventory_type, grade, quantity_owned,
                   quantity_in_stock, reorder_level, description, unit_of_measure,
                   storage_location, unit_price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name, category, inventory_type, grade, stock, stock, reorder,
                    description, unit, storage_location or None, unit_price,
                ),
            )
            resource_id = cursor.lastrowid
            cursor.execute(
                """
                UPDATE resource_request
                SET resource_id = %s, category = %s
                WHERE resource_id IS NULL AND status = 'In review'
                  AND LOWER(TRIM(resource_name)) = LOWER(TRIM(%s))
                """,
                (resource_id, category, name),
            )
            if stock:
                record_inventory_adjustment(
                    cursor, resource_id, None, "manual", stock, 0, stock,
                    "Initial stock entered when item was added", user["id"],
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message=f"{name} added to the inventory.", id=resource_id), 201


@inventory_bp.put("/api/inventory/<int:item_id>")
@api_route("ltsm")
def api_update_inventory(user, item_id):
    v = Validator(json_body())
    name = v.text("item_name", "Item name", 1, 100)
    category = v.choice("category", "Category", CATEGORIES)
    grade = v.text("grade", "Grade", 1, 20) if category == "Textbooks" else None
    inventory_type = v.choice("inventory_type", "Inventory type", ("consumable", "non_consumable"))
    reorder = v.integer("reorder_level", "Reorder level", 0, 10000)
    description = v.text("description", "Description", 0, 255)
    unit = v.text("unit", "Unit", 0, 45) or "units"
    storage_location = v.text("storage_location", "Storage location", 0, 120)
    raw_unit_price = v.data.get("unit_price")
    unit_price = (
        None if raw_unit_price in (None, "")
        else v.decimal("unit_price", "Unit price", 0, 99999999.99)
    )
    v.done()

    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT resource_id, category, grade FROM resource WHERE resource_id = %s FOR UPDATE",
                (item_id,),
            )
            current_item = cursor.fetchone()
            if current_item is None:
                raise ApiError("That inventory item does not exist.", 404)
            if category == "Textbooks" and not is_foundation_phase_grade(grade):
                if current_item["category"] != "Textbooks" or grade != current_item["grade"]:
                    raise ApiError(
                        "New and reclassified books must be for Grade 1, Grade 2, or Grade 3.",
                        400,
                        {"grade": "Choose Grade 1, Grade 2, or Grade 3."},
                    )
            if category != "Textbooks":
                grade = None
            cursor.execute(
                """
                SELECT resource_id FROM resource
                WHERE LOWER(resource_name) = LOWER(%s) AND resource_id <> %s
                LIMIT 1
                """,
                (name, item_id),
            )
            if cursor.fetchone():
                raise ApiError(f"{name} is already in the inventory.", 409, {"item_name": "Already exists."})
            cursor.execute(
                """
                UPDATE resource
                SET resource_name = %s, category = %s, inventory_type = %s, grade = %s,
                    reorder_level = %s, description = %s, unit_of_measure = %s,
                    storage_location = %s, unit_price = %s
                WHERE resource_id = %s
                """,
                (
                    name, category, inventory_type, grade, reorder, description, unit,
                    storage_location or None, unit_price, item_id,
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message=f"{name} updated.")


def record_inventory_adjustment(cursor, resource_id, movement_id, kind, quantity_change,
                                quantity_before, quantity_after, reason, user_id,
                                quantity_owned_before=None, quantity_owned_after=None):
    cursor.execute(
        """
        INSERT INTO inventory_adjustment
          (resource_id, movement_id, adjustment_type, quantity_change,
           quantity_before, quantity_after, quantity_owned_before,
           quantity_owned_after, reason, recorded_by_user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            resource_id, movement_id, kind, quantity_change,
            quantity_before, quantity_after, quantity_owned_before,
            quantity_owned_after, reason, user_id,
        ),
    )


def locked_reserved_quantity(cursor, resource_id):
    cursor.execute(
        """
        SELECT allocated_quantity
        FROM resource_request
        WHERE resource_id = %s AND status = 'Ready for collection'
        FOR UPDATE
        """,
        (resource_id,),
    )
    return sum(row["allocated_quantity"] or 0 for row in cursor.fetchall())


@inventory_bp.get("/api/inventory/adjustments")
@api_route("ltsm")
def api_inventory_adjustments(user):
    items = db.query_all(
        """
        SELECT r.resource_name AS item, a.adjustment_type,
               a.quantity_change, a.quantity_before, a.quantity_after,
               a.quantity_owned_after,
               a.reason, COALESCE(u.full_name, 'Former user') AS recorded_by,
               DATE_FORMAT(a.created_at, '%%Y-%%m-%%d %%H:%%i') AS adjusted_at
        FROM inventory_adjustment AS a
        JOIN resource AS r ON r.resource_id = a.resource_id
        LEFT JOIN users AS u ON u.user_id = a.recorded_by_user_id
        ORDER BY a.created_at DESC, a.adjustment_id DESC
        LIMIT 100
        """
    )
    return jsonify(items=items)


@inventory_bp.post("/api/inventory/adjust")
@api_route("ltsm")
def api_adjust_inventory(user):
    v = Validator(json_body())
    item_id = v.integer("item_id", "Item", 1, 10**9)
    action = v.choice("action", "Adjustment", ("receive", "add", "remove", "damaged", "lost", "obsolete"))
    quantity = v.integer("quantity", "Quantity", 1, 10000)
    reason = v.text("reason", "Reason", 3, 255)
    v.done()

    quantity_change = quantity if action in ("receive", "add") else -quantity
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT resource_id, resource_name, quantity_in_stock, quantity_owned
                FROM resource
                WHERE resource_id = %s
                FOR UPDATE
                """,
                (item_id,),
            )
            item = cursor.fetchone()
            if not item:
                raise ApiError("Choose an item from the inventory.", 404)

            item["available_stock"] = item["quantity_in_stock"] - locked_reserved_quantity(cursor, item_id)
            quantity_after = item["quantity_in_stock"] + quantity_change
            if action not in ("receive", "add") and quantity > item["available_stock"]:
                raise ApiError(
                    f"Only {item['available_stock']} of {item['resource_name']} are available to adjust.",
                    409,
                    {"quantity": "Cannot remove stock already allocated to requests."},
                )
            if action in ("receive", "add"):
                cursor.execute(
                    """
                    UPDATE resource
                    SET quantity_in_stock = %s, quantity_owned = quantity_owned + %s
                    WHERE resource_id = %s
                    """,
                    (quantity_after, quantity, item_id),
                )
                kind = "received"
            else:
                cursor.execute(
                    "UPDATE resource SET quantity_in_stock = %s WHERE resource_id = %s",
                    (quantity_after, item_id),
                )
                kind = "manual" if action == "remove" else action
            available_after = quantity_after - (
                item["quantity_in_stock"] - item["available_stock"]
            )
            record_inventory_adjustment(
                cursor, item_id, None, kind, quantity_change,
                item["quantity_in_stock"], quantity_after, reason, user["id"],
            )
        connection.commit()
        verb = {
            "receive": "received into",
            "add": "received into",
            "remove": "removed from",
            "damaged": "written off as damaged from",
            "lost": "written off as lost from",
            "obsolete": "written off as obsolete from",
        }[action]
        return jsonify(
            message=f"{quantity} × {item['resource_name']} {verb} stock. "
                    f"Available stock is now {available_after}."
        ), 200
    except Exception:
        connection.rollback()
        raise


def loan_status(loan):
    if not loan["due"]:
        return "On loan", "ok"
    remaining = (date.fromisoformat(loan["due"]) - today()).days
    if remaining < 0:
        return "Overdue", "danger"
    return ("Due soon", "warning") if remaining <= 3 else ("On loan", "ok")


@circulation_bp.get("/api/loans")
@api_route("ltsm")
def api_loans(user):
    rows = db.query_all(
        """
        SELECT m.movement_id AS id, m.borrower_id, m.borrower_name AS borrower,
               m.resource_id AS item_id, r.resource_name AS item,
               m.movement_date AS issued,
               CAST(COALESCE(m.issued_quantity, m.quantity) - COALESCE(SUM(e.quantity), 0) AS SIGNED) AS quantity,
               m.due_date AS due
        FROM item_movement AS m
        JOIN resource AS r ON r.resource_id = m.resource_id
        LEFT JOIN item_movement AS e
          ON e.related_issue_movement_id = m.movement_id
         AND e.movement_type IN ('return', 'lost', 'damaged')
        WHERE m.movement_type = 'issue' AND m.active_loan = TRUE
        GROUP BY m.movement_id, m.borrower_id, m.borrower_name, m.resource_id,
                 r.resource_name, m.movement_date, m.issued_quantity, m.quantity, m.due_date
        HAVING quantity > 0
        ORDER BY m.due_date, m.movement_date, m.movement_id
        """
    )
    items = []
    for loan in rows:
        loan["issued"] = date_value(loan["issued"])
        loan["due"] = date_value(loan["due"]) if loan["due"] else None
        label, tone = loan_status(loan)
        items.append({
            "id": loan["id"], "borrower_id": loan["borrower_id"],
            "borrower": loan["borrower"], "item_id": loan["item_id"],
            "item": loan["item"], "quantity": loan["quantity"],
            "issued": loan["issued"], "due": loan["due"],
            "status": label, "tone": tone,
        })
    return jsonify(items=items)


@circulation_bp.get("/api/borrowers")
@api_route("ltsm")
def api_borrowers(user):
    rows = db.query_all(
        """
        SELECT school_id AS id, full_name AS name, role
        FROM users
        WHERE role IN ('learner', 'staff') AND is_active = TRUE
        ORDER BY full_name, school_id
        """
    )
    return jsonify(items=rows)


@circulation_bp.get("/api/movement-history")
@api_route("ltsm")
def api_movement_history(user):
    query = request.args.get("q", "").strip()[:100]
    search = f"%{query}%"
    sql = """
        SELECT m.movement_id AS id, m.related_issue_movement_id AS issue_id,
               m.movement_type, m.borrower_id, m.borrower_name AS borrower,
               r.resource_name AS item, m.quantity, m.movement_date AS date,
               m.due_date AS due, m.reason,
               COALESCE(u.full_name, 'Former user') AS recorded_by,
               DATE_FORMAT(m.created_at, '%%Y-%%m-%%d %%H:%%i') AS recorded_at
        FROM item_movement AS m
        JOIN resource AS r ON r.resource_id = m.resource_id
        LEFT JOIN users AS u ON u.user_id = m.recorded_by_user_id
        WHERE (%s = ''
           OR m.borrower_id LIKE %s
           OR m.borrower_name LIKE %s
           OR r.resource_name LIKE %s
           OR COALESCE(m.reason, '') LIKE %s)
        ORDER BY m.movement_date DESC, m.movement_id DESC
        """
    if not query:
        sql += " LIMIT 200"
    rows = db.query_all(
        sql,
        (query, search, search, search, search),
    )
    for row in rows:
        row["date"] = date_value(row["date"])
        row["due"] = date_value(row["due"]) if row["due"] else None
    return jsonify(items=rows)


@circulation_bp.post("/api/movements")
@api_route("ltsm")
def api_movement(user):
    data = json_body()
    v = Validator(data)
    kind = v.choice("movement_type", "Action", ("issue", "return", "lost", "damaged"))
    quantity = v.integer("quantity", "Quantity", 1, 100)
    moved_on = v.day("movement_date", "Date", not_after=today())
    if kind == "issue":
        item_id = v.integer("item_id", "Item", 1, 10**9)
        borrower_id = v.text("borrower_id", "Recipient", 1, 40)
        due = v.day("due_date", "Due date", not_before=moved_on)
        loan_id = None
        reason = None
    else:
        loan_id = v.integer("loan_id", "Outstanding loan", 1, 10**9)
        item_id = borrower_id = due = None
        reason = v.text("reason", "Reason", 3, 255) if kind in ("lost", "damaged") else ""
    v.done()
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            if kind == "issue":
                cursor.execute(
                    """
                    SELECT resource_id AS id, resource_name AS name, category,
                           quantity_in_stock AS stock, quantity_owned AS owned
                    FROM resource WHERE resource_id = %s FOR UPDATE
                    """,
                    (item_id,),
                )
                item = cursor.fetchone()
                if not item:
                    raise ApiError("Choose an item from the list.", 400, {"item_id": "Unknown item."})
                item["available_stock"] = item["stock"] - locked_reserved_quantity(cursor, item_id)
                if quantity > item["available_stock"]:
                    raise ApiError(
                        f"Only {item['available_stock']} of {item['name']} are available; some stock is allocated to requests.",
                        409,
                        {"quantity": "Not enough stock."},
                    )
                cursor.execute(
                    """
                    SELECT user_id, full_name, school_id
                    FROM users
                    WHERE LOWER(school_id) = LOWER(%s)
                      AND role IN ('learner', 'staff') AND is_active = TRUE
                    LIMIT 1
                    """,
                    (borrower_id,),
                )
                borrower_row = cursor.fetchone()
                if not borrower_row:
                    raise ApiError(
                        "Select an active teacher or learner from the recipient list.",
                        400,
                        {"borrower_id": "Recipient not found or inactive."},
                    )
                borrower = borrower_row["full_name"]
                borrower_id = borrower_row["school_id"]
                cursor.execute(
                    "UPDATE resource SET quantity_in_stock = quantity_in_stock - %s WHERE resource_id = %s",
                    (quantity, item_id),
                )
                cursor.execute(
                    """
                    INSERT INTO item_movement
                      (resource_id, borrower_user_id, borrower_id, borrower_name, movement_type,
                       quantity, issued_quantity, movement_date, due_date,
                       active_loan, recorded_by_user_id)
                    VALUES (%s, %s, %s, %s, 'issue', %s, %s, %s, %s, TRUE, %s)
                    """,
                    (
                        item_id, borrower_row["user_id"], borrower_id, borrower,
                        quantity, quantity, moved_on, due, user["id"],
                    ),
                )
                record_inventory_adjustment(
                    cursor, item_id, cursor.lastrowid, "issue", -quantity,
                    item["stock"], item["stock"] - quantity,
                    f"Issued to {borrower} ({borrower_id}); due {due.isoformat()}",
                    user["id"],
                )
                connection.commit()
                return jsonify(message=f"Issued {quantity} × {item['name']} to {borrower}, due {due.isoformat()}."), 201

            cursor.execute(
                """
                SELECT resource_id FROM item_movement
                WHERE movement_id = %s AND movement_type = 'issue'
                """,
                (loan_id,),
            )
            loan_ref = cursor.fetchone()
            if not loan_ref:
                raise ApiError("Choose an outstanding issue from the loan list.", 404)
            cursor.execute(
                """
                SELECT resource_id, resource_name, quantity_in_stock AS stock,
                       quantity_owned AS owned
                FROM resource WHERE resource_id = %s FOR UPDATE
                """,
                (loan_ref["resource_id"],),
            )
            item = cursor.fetchone()
            cursor.execute(
                """
                SELECT movement_id, resource_id, borrower_user_id, borrower_id, borrower_name,
                       quantity, issued_quantity, movement_date, due_date, active_loan
                FROM item_movement
                WHERE movement_id = %s AND movement_type = 'issue'
                FOR UPDATE
                """,
                (loan_id,),
            )
            loan = cursor.fetchone()
            if moved_on < loan["movement_date"]:
                raise ApiError("A return or loss/damage report cannot be dated before the original issue.", 400)
            cursor.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) AS quantity
                FROM item_movement
                WHERE related_issue_movement_id = %s
                  AND movement_type IN ('return', 'lost', 'damaged')
                """,
                (loan_id,),
            )
            already_resolved = cursor.fetchone()["quantity"]
            outstanding = (loan["issued_quantity"] or loan["quantity"]) - already_resolved
            if not loan["active_loan"] or outstanding <= 0:
                raise ApiError("That issue has no outstanding quantity.", 409)
            if quantity > outstanding:
                raise ApiError(
                    f"Only {outstanding} of {item['resource_name']} are outstanding on this issue.",
                    409,
                    {"quantity": "Too many."},
                )
            remaining = outstanding - quantity
            borrower_name = loan["borrower_name"]
            if kind == "return":
                cursor.execute(
                    "UPDATE resource SET quantity_in_stock = quantity_in_stock + %s WHERE resource_id = %s",
                    (quantity, loan["resource_id"]),
                )
            else:
                if quantity > item["owned"] or item["owned"] - quantity < item["stock"]:
                    raise ApiError("The inventory's owned quantity is inconsistent with this outstanding loan.", 409)
                cursor.execute(
                    "UPDATE resource SET quantity_owned = quantity_owned - %s WHERE resource_id = %s",
                    (quantity, loan["resource_id"]),
                )
            cursor.execute(
                """
                INSERT INTO item_movement
                  (resource_id, borrower_user_id, borrower_id, borrower_name, movement_type,
                   quantity, movement_date, related_issue_movement_id, reason,
                   active_loan, recorded_by_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s)
                """,
                (
                    loan["resource_id"], loan["borrower_user_id"],
                    loan["borrower_id"], borrower_name,
                    kind, quantity, moved_on, loan_id, reason or None, user["id"],
                ),
            )
            movement_id = cursor.lastrowid
            if kind == "return":
                record_inventory_adjustment(
                    cursor, loan["resource_id"], movement_id, "return", quantity,
                    item["stock"], item["stock"] + quantity,
                    f"Returned by {borrower_name} ({loan['borrower_id']}); issue #{loan_id}",
                    user["id"],
                )
            else:
                record_inventory_adjustment(
                    cursor, loan["resource_id"], movement_id, kind, -quantity,
                    None, None,
                    f"{quantity} × {item['resource_name']} marked {kind} while issued to "
                    f"{borrower_name} ({loan['borrower_id']}); issue #{loan_id}. {reason}",
                    user["id"], item["owned"], item["owned"] - quantity,
                )
            cursor.execute(
                "UPDATE item_movement SET active_loan = %s WHERE movement_id = %s",
                (remaining > 0, loan_id),
            )
        connection.commit()
        description = {
            "return": f"Returned {quantity} × {item['resource_name']} from {borrower_name}.",
            "lost": f"Recorded {quantity} × {item['resource_name']} as lost from {borrower_name}'s loan.",
            "damaged": f"Recorded {quantity} × {item['resource_name']} as damaged from {borrower_name}'s loan.",
        }[kind]
        return jsonify(message=description), 201
    except Exception:
        connection.rollback()
        raise


@maintenance_bp.get("/api/maintenance")
@api_route("ltsm")
def api_maintenance(user):
    rows = db.query_all(
        """
        SELECT issue_id AS id, equipment_or_item AS item,
               description AS issue, reported_date AS reported, status, priority
        FROM maintenance_issue
        ORDER BY reported_date DESC, issue_id DESC
        """
    )
    for row in rows:
        row["reported"] = date_value(row["reported"])
    this_month = today().strftime("%Y-%m")
    summary = {
        "open": sum(row["status"] == "Open" for row in rows),
        "in_repair": sum(row["status"] == "In repair" for row in rows),
        "resolved": sum(row["status"] == "Resolved" and row["reported"].startswith(this_month) for row in rows),
        "out_of_service": sum(row["status"] == "Out of service" for row in rows),
    }
    items = [{**row, "tone": MAINTENANCE_TONES[row["status"]]} for row in rows]
    return jsonify(items=items, summary=summary)


@maintenance_bp.post("/api/maintenance")
@api_route("ltsm")
def api_log_maintenance(user):
    v = Validator(json_body())
    row = {
        "item": v.text("equipment", "Equipment / item", 1, 100),
        "reported_by": v.text("reported_by", "Reported by", 1, 80),
        "priority": v.choice("priority", "Priority", ("Low", "Normal", "High", "Urgent")),
        "reported": (v.day("date", "Date reported", not_after=today()) or today()).isoformat(),
        "issue": v.text("description", "Description", 10, 500),
        "status": "Open",
    }
    v.done()
    issue_id = db.execute(
        """
        INSERT INTO maintenance_issue
          (equipment_or_item, reported_by_user_id, reported_by_name, priority,
           reported_date, description, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'Open')
        """,
        (
            row["item"], user["id"], row["reported_by"], row["priority"],
            row["reported"], row["issue"],
        ),
    )
    return jsonify(message=f"Issue logged for {row['item']}.", id=issue_id), 201


# --------------------------------------------------------------------------- #
# Task 3B: approval workflows, dashboard KPIs and reports
# --------------------------------------------------------------------------- #
def request_priority(row):
    """Priority comes from how soon the resource is needed (the request form has no priority field)."""
    needed = row.get("needed_by")
    if not needed:
        return "Normal", "ok"
    days_left = (date.fromisoformat(needed) - today()).days
    if days_left <= 3:
        return "High", "danger"
    return ("Medium", "warning") if days_left <= 7 else ("Normal", "ok")


def plural(count, singular, many=None):
    return f"{count} {singular if count == 1 else (many or singular + 's')}"


@requests_bp.get("/api/committee/requests")
@api_route("ltsm")
def api_committee_requests(user):
    status = request.args.get("status", "").strip()
    sql = """
        SELECT rr.request_id AS id, rr.resource_id, rr.resource_name AS name,
               rr.category, rr.purpose, u.full_name AS requested_by,
               u.school_id AS requester_id, rr.submitted_date AS submitted,
               rr.submitted_at,
               rr.needed_by, rr.quantity, rr.allocated_quantity,
               rr.collection_slot, rr.collection_location_id,
               cl.location_name AS collection_location,
               rr.status, rr.latest_update,
               r.unit_of_measure AS unit,
               CAST(r.quantity_in_stock - COALESCE((
                   SELECT SUM(allocated.allocated_quantity)
                   FROM resource_request AS allocated
                   WHERE allocated.resource_id = r.resource_id
                     AND allocated.status = 'Ready for collection'
               ), 0) AS SIGNED) AS available_stock
        FROM resource_request AS rr
        JOIN users AS u ON u.user_id = rr.user_id
        LEFT JOIN resource AS r ON r.resource_id = rr.resource_id
        LEFT JOIN collection_location AS cl
          ON cl.location_id = rr.collection_location_id
    """
    params = []
    if status:
        sql += " WHERE rr.status = %s"
        params.append(status)
    sql += " ORDER BY rr.submitted_at ASC, rr.request_id ASC"
    rows = db.query_all(sql, params)
    items = []
    for r in rows:
        r["submitted"] = date_value(r["submitted"])
        r["submitted_at"] = datetime_value(r["submitted_at"])
        r["needed_by"] = date_value(r["needed_by"]) if r["needed_by"] else None
        r["collection_slot"] = (
            r["collection_slot"].isoformat(sep=" ", timespec="minutes")
            if r["collection_slot"] else None
        )
        priority, tone = request_priority(r)
        items.append({
            "id": r["id"], "resource_id": r["resource_id"], "name": r["name"],
            "category": r["category"], "purpose": r["purpose"],
            "requested_by": r["requested_by"], "requester_id": r["requester_id"],
            "submitted": r["submitted"], "submitted_at": r["submitted_at"],
            "needed_by": r["needed_by"],
            "quantity": r["quantity"], "allocated_quantity": r["allocated_quantity"],
            "collection_slot": r["collection_slot"], "status": r["status"],
            "collection_location_id": r["collection_location_id"],
            "collection_location": r["collection_location"],
            "available_stock": r["available_stock"], "unit": r["unit"],
            "priority": priority, "priority_tone": tone,
            "latest_update": r["latest_update"],
        })
    return jsonify(items=items)


@requests_bp.get("/api/collection-locations")
@api_route("ltsm")
def api_collection_locations(user):
    rows = db.query_all(
        """
        SELECT location_id AS id, location_name AS name
        FROM collection_location
        WHERE is_active = TRUE
        ORDER BY location_name
        """
    )
    return jsonify(items=rows)


@catalog_bp.get("/api/committee/suggestions")
@api_route("ltsm")
def api_committee_suggestions(user):
    rows = db.query_all(
        """
        SELECT s.suggestion_id AS id, s.resource_name AS name,
               s.message, COALESCE(u.full_name, s.submitter_name, 'Anonymous') AS submitted_by,
               s.created_at AS submitted
        FROM resource_suggestion AS s
        LEFT JOIN users AS u ON u.user_id = s.user_id
        ORDER BY s.created_at DESC, s.suggestion_id DESC
        """
    )
    for row in rows:
        row["submitted"] = (
            row["submitted"].isoformat(sep=" ", timespec="minutes")
            if hasattr(row["submitted"], "isoformat")
            else row["submitted"]
        )
    return jsonify(items=rows)


@requests_bp.post("/api/requests/<int:request_id>/decision")
@api_route("ltsm")
def api_decide_request(user, request_id):
    v = Validator(json_body())
    decision = v.choice("decision", "Decision", ("Approved", "Declined"))
    collection_slot = None
    collection_location_id = None
    if decision == "Approved":
        slot_value = v.text("collection_slot", "Collection date and time", 1, 16)
        collection_location_id = v.integer(
            "collection_location_id", "Collection location", 1, 2147483647
        )
        try:
            collection_slot = datetime.strptime(slot_value, "%Y-%m-%dT%H:%M")
        except ValueError:
            v._fail("collection_slot", "Enter a valid collection date and time.")
        if collection_slot and collection_slot <= now().replace(tzinfo=None):
            v._fail("collection_slot", "Collection must be scheduled for a future date and time.")
    v.done()
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            inventory_item = None
            if decision == "Approved":
                cursor.execute(
                    "SELECT resource_id FROM resource_request WHERE request_id = %s",
                    (request_id,),
                )
                request_ref = cursor.fetchone()
                if request_ref is None:
                    raise ApiError("That request does not exist.", 404)
                if request_ref["resource_id"] is not None:
                    cursor.execute(
                        """
                        SELECT resource_id, resource_name, quantity_in_stock, unit_of_measure
                        FROM resource WHERE resource_id = %s FOR UPDATE
                        """,
                        (request_ref["resource_id"],),
                    )
                    inventory_item = cursor.fetchone()
            cursor.execute(
                """
                SELECT request_id, user_id, resource_id, resource_name, quantity,
                       allocated_quantity, status, submitted_at
                FROM resource_request WHERE request_id = %s FOR UPDATE
                """,
                (request_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ApiError("That request does not exist.", 404)
            legacy_unallocated = (
                row["status"] in ("Approved", "Ready for collection")
                and row["allocated_quantity"] is None
            )
            if row["status"] != "In review" and not legacy_unallocated:
                raise ApiError(f"{row['resource_name']} was already {row['status'].lower()}.", 409)

            if decision == "Approved" and row["resource_id"] is not None:
                cursor.execute(
                    """
                    SELECT request_id, resource_name
                    FROM resource_request
                    WHERE resource_id = %s AND status = 'In review'
                      AND (
                        submitted_at < %s
                        OR (submitted_at = %s AND request_id < %s)
                      )
                    ORDER BY submitted_at ASC, request_id ASC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        row["resource_id"], row["submitted_at"],
                        row["submitted_at"], request_id,
                    ),
                )
                earlier_request = cursor.fetchone()
                if earlier_request:
                    raise ApiError(
                        f"Review earlier request #{earlier_request['request_id']} for "
                        f"{earlier_request['resource_name']} first to keep allocation first-come, first-served.",
                        409,
                    )

            if decision == "Declined":
                cursor.execute(
                    """
                    UPDATE resource_request
                    SET status = 'Declined', allocated_quantity = NULL,
                        collection_slot = NULL, collection_location_id = NULL,
                        latest_update = 'Declined by the LTSM committee'
                    WHERE request_id = %s
                    """,
                    (request_id,),
                )
                message = f"{row['resource_name']} declined."
                notification_status = "Declined"
                notification_message = (
                    f"Your request for {row['resource_name']} was declined by the LTSM committee."
                )
            else:
                if row["resource_id"] is None:
                    raise ApiError(
                        f"{row['resource_name']} is not linked to an inventory item and cannot be allocated.",
                        409,
                    )
                if inventory_item is None:
                    raise ApiError("The requested inventory item no longer exists.", 409)
                cursor.execute(
                    """
                    SELECT location_name FROM collection_location
                    WHERE location_id = %s AND is_active = TRUE
                    """,
                    (collection_location_id,),
                )
                location = cursor.fetchone()
                if location is None:
                    raise ApiError(
                        "Choose an active collection location.",
                        400,
                        {"collection_location_id": "Select an available collection location."},
                    )
                reserved = locked_reserved_quantity(cursor, row["resource_id"])
                available = inventory_item["quantity_in_stock"] - reserved
                if row["quantity"] > available:
                    raise ApiError(
                        f"Only {available} {inventory_item['unit_of_measure']} are available; "
                        f"{row['quantity']} were requested.",
                        409,
                        {"decision": "Insufficient available stock to approve this request."},
                    )
                formatted_slot = collection_slot.strftime("%d %b %Y at %H:%M")
                update = (
                    f"{row['quantity']} {inventory_item['unit_of_measure']} allocated; "
                    f"collect {formatted_slot} at {location['location_name']}"
                )
                cursor.execute(
                    """
                    UPDATE resource_request
                    SET status = 'Ready for collection', allocated_quantity = quantity,
                        collection_slot = %s, collection_location_id = %s,
                        latest_update = %s, ready_at = %s
                    WHERE request_id = %s
                    """,
                    (
                        collection_slot, collection_location_id, update,
                        now().replace(tzinfo=None), request_id,
                    ),
                )
                message = (
                    f"{row['resource_name']} allocated. Collection is scheduled for "
                    f"{formatted_slot} at {location['location_name']}."
                )
                notification_status = "Ready for collection"
                notification_message = (
                    f"Your request for {row['resource_name']} was approved. "
                    f"Collect it on {formatted_slot} at {location['location_name']}."
                )
            cursor.execute(
                "SELECT email FROM users WHERE user_id = %s",
                (row["user_id"],),
            )
            requester = cursor.fetchone()
            create_notification(
                cursor,
                row["user_id"],
                "my-requests",
                f"Request {notification_status.lower()}",
                notification_message,
                "/my-requests.html",
            )
        connection.commit()
        if requester:
            send_email(
                requester["email"],
                f"Request {notification_status.lower()} - {row['resource_name']}",
                f"{notification_message}\n\nRequest reference: #{request_id}",
            )
        return jsonify(message=message)
    except Exception:
        connection.rollback()
        raise


@requests_bp.post("/api/committee/requests/<int:request_id>/fulfill")
@api_route("ltsm")
def api_fulfill_request(user, request_id):
    data = json_body()
    v = Validator(data)
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT resource_id FROM resource_request WHERE request_id = %s",
                (request_id,),
            )
            request_ref = cursor.fetchone()
            if request_ref is None:
                raise ApiError("That request does not exist.", 404)
            if request_ref["resource_id"] is None:
                raise ApiError("This request is not linked to an inventory item.", 409)
            cursor.execute(
                """
                SELECT resource_id, resource_name, quantity_in_stock
                FROM resource WHERE resource_id = %s FOR UPDATE
                """,
                (request_ref["resource_id"],),
            )
            item = cursor.fetchone()
            if item is None:
                raise ApiError("The allocated inventory item no longer exists.", 409)
            cursor.execute(
                """
                SELECT rr.request_id, rr.user_id, rr.resource_id, rr.resource_name,
                       rr.allocated_quantity, rr.status, rr.category,
                       u.full_name, u.school_id, u.email
                FROM resource_request AS rr
                JOIN users AS u ON u.user_id = rr.user_id
                WHERE rr.request_id = %s
                FOR UPDATE
                """,
                (request_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ApiError("That request does not exist.", 404)
            if row["status"] != "Ready for collection" or not row["allocated_quantity"]:
                raise ApiError("Only allocated requests can be marked fulfilled.", 409)
            is_loan = row["category"] in ("Textbooks", "Equipment")
            due = v.day("due_date", "Expected return date", not_before=today()) if is_loan else None
            v.done()
            if item["quantity_in_stock"] < row["allocated_quantity"]:
                raise ApiError("The allocated stock is no longer available; review the inventory.", 409)

            stock_after = item["quantity_in_stock"] - row["allocated_quantity"]
            cursor.execute(
                "UPDATE resource SET quantity_in_stock = %s WHERE resource_id = %s",
                (stock_after, item["resource_id"]),
            )
            cursor.execute(
                """
                INSERT INTO item_movement
                  (resource_id, borrower_user_id, borrower_id, borrower_name, movement_type,
                   quantity, issued_quantity, movement_date, due_date,
                   active_loan, recorded_by_user_id)
                VALUES (%s, %s, %s, %s, 'issue', %s, %s, %s, %s, %s, %s)
                """,
                (
                    item["resource_id"], row["user_id"], row["school_id"], row["full_name"],
                    row["allocated_quantity"], row["allocated_quantity"], today(), due,
                    is_loan, user["id"],
                ),
            )
            record_inventory_adjustment(
                cursor, item["resource_id"], cursor.lastrowid, "issue",
                -row["allocated_quantity"], item["quantity_in_stock"], stock_after,
                f"Fulfilled request #{request_id} for {row['full_name']} ({row['school_id']})",
                user["id"],
            )
            cursor.execute(
                """
                UPDATE resource_request
                SET status = 'Fulfilled',
                    fulfilled_at = %s,
                    latest_update = CONCAT('Fulfilled: ', allocated_quantity, ' allocated unit(s) issued on ', %s)
                WHERE request_id = %s AND status = 'Ready for collection'
                """,
                (now().replace(tzinfo=None), today().isoformat(), request_id),
            )
            fulfillment_message = (
                f"Your request for {row['resource_name']} has been fulfilled. "
                f"{row['allocated_quantity']} unit(s) were issued."
            )
            create_notification(
                cursor,
                row["user_id"],
                "my-requests",
                "Request fulfilled",
                fulfillment_message,
                "/my-requests.html",
            )
        connection.commit()
        send_email(
            row["email"],
            f"Request fulfilled - {row['resource_name']}",
            f"{fulfillment_message}\n\nRequest reference: #{request_id}",
        )
        return jsonify(message=f"{row['allocated_quantity']} × {item['resource_name']} issued to {row['full_name']}.")
    except Exception:
        connection.rollback()
        raise


@bookings_bp.get("/api/committee/bookings")
@api_route("ltsm")
def api_committee_bookings(user):
    status = request.args.get("status", "").strip()
    include_all = request.args.get("all", "").lower() in ("1", "true", "yes")
    conditions, params = [], []
    if not include_all:
        conditions.append("b.booking_date >= %s")
        params.append(today())
    if status:
        if status not in ("Awaiting approval", "Confirmed", "Declined"):
            raise ApiError("Choose a valid booking status.")
        conditions.append("b.status = %s")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    date_order = "DESC" if include_all else "ASC"
    rows = db.query_all(
        f"""
        SELECT b.booking_id AS id, r.resource_name AS equipment,
               u.full_name AS booked_by, b.booking_date AS `date`,
               b.start_time AS `start`, b.end_time AS `end`, b.room, b.status
        FROM equipment_booking AS b
        JOIN resource AS r ON r.resource_id = b.resource_id
        JOIN users AS u ON u.user_id = b.user_id
        {where_clause}
        ORDER BY b.booking_date {date_order}, b.start_time, b.booking_id
        """,
        params,
    )
    return jsonify(items=[
        {
            **booking,
            "date": date_value(booking["date"]),
            "start": time_value(booking["start"]),
            "end": time_value(booking["end"]),
            "tone": BOOKING_TONES[booking["status"]],
        }
        for booking in rows
    ])


@bookings_bp.post("/api/bookings/<int:booking_id>/decision")
@api_route("ltsm")
def api_decide_booking(user, booking_id):
    v = Validator(json_body())
    decision = v.choice("decision", "Decision", ("Confirmed", "Declined"))
    v.done()
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT resource_id FROM equipment_booking WHERE booking_id = %s",
                (booking_id,),
            )
            booking_ref = cursor.fetchone()
            if booking_ref is None:
                raise ApiError("That booking does not exist.", 404)
            cursor.execute(
                """
                SELECT resource_id, resource_name, quantity_in_stock
                FROM resource WHERE resource_id = %s FOR UPDATE
                """,
                (booking_ref["resource_id"],),
            )
            equipment = cursor.fetchone()
            cursor.execute(
                """
                SELECT eb.booking_id, eb.user_id, eb.resource_id, eb.booking_date,
                       eb.start_time, eb.end_time, eb.status, u.email
                FROM equipment_booking AS eb
                JOIN users AS u ON u.user_id = eb.user_id
                WHERE eb.booking_id = %s
                FOR UPDATE
                """,
                (booking_id,),
            )
            booking = cursor.fetchone()
            if booking is None:
                raise ApiError("That booking does not exist.", 404)

            if decision == "Confirmed":
                if booking["status"] != "Awaiting approval":
                    raise ApiError(f"That booking was already {booking['status'].lower()}.", 409)
                if equipment is None:
                    raise ApiError("The booked equipment no longer exists.", 409)
                cursor.execute(
                    """
                    SELECT COUNT(*) AS booking_count
                    FROM equipment_booking
                    WHERE resource_id = %s
                      AND booking_date BETWEEN DATE_SUB(%s, INTERVAL 1 DAY)
                                           AND DATE_ADD(%s, INTERVAL 1 DAY)
                      AND booking_id <> %s AND status != 'Declined'
                      AND TIMESTAMP(booking_date, start_time)
                          < DATE_ADD(%s, INTERVAL 20 MINUTE)
                      AND DATE_ADD(TIMESTAMP(booking_date, end_time), INTERVAL 20 MINUTE) > %s
                    """,
                    (
                        booking["resource_id"], booking["booking_date"],
                        booking["booking_date"], booking_id,
                        datetime.combine(
                            booking["booking_date"],
                            datetime.strptime(time_value(booking["end_time"]), "%H:%M").time(),
                        ),
                        datetime.combine(
                            booking["booking_date"],
                            datetime.strptime(time_value(booking["start_time"]), "%H:%M").time(),
                        ),
                    ),
                )
                overlapping = cursor.fetchone()["booking_count"]
                if overlapping >= equipment["quantity_in_stock"]:
                    raise ApiError(
                        f"No {equipment['resource_name']} is free during this booking time. "
                        "Another booking already occupies the available equipment.",
                        409,
                        {"decision": "This booking overlaps another reservation."},
                    )
                cursor.execute(
                    "UPDATE equipment_booking SET status = 'Confirmed' WHERE booking_id = %s AND status = 'Awaiting approval'",
                    (booking_id,),
                )
                message = f"{equipment['resource_name']} booking confirmed."
            else:
                if booking["status"] == "Declined":
                    raise ApiError("That booking has already been cancelled or declined.", 409)
                if booking["status"] == "Confirmed":
                    start_time = booking["start_time"]
                    start_time_text = (
                        start_time.strftime("%H:%M:%S")
                        if hasattr(start_time, "strftime")
                        else str(start_time)
                    )
                    booking_datetime = datetime.combine(
                        booking["booking_date"],
                        datetime.strptime(start_time_text, "%H:%M:%S").time(),
                    )
                    if booking_datetime <= now().replace(tzinfo=None):
                        raise ApiError("A confirmed booking cannot be cancelled after it has started.", 409)
                cursor.execute(
                    "UPDATE equipment_booking SET status = 'Declined' WHERE booking_id = %s AND status <> 'Declined'",
                    (booking_id,),
                )
                message = (
                    f"{equipment['resource_name']} booking cancelled."
                    if booking["status"] == "Confirmed"
                    else f"{equipment['resource_name']} booking declined."
                )
            notification_title = (
                "Booking confirmed"
                if decision == "Confirmed"
                else "Booking cancelled" if booking["status"] == "Confirmed"
                else "Booking declined"
            )
            notification_message = (
                f"Your {equipment['resource_name']} booking on "
                f"{date_value(booking['booking_date'])} is "
                f"{'confirmed' if decision == 'Confirmed' else 'cancelled' if booking['status'] == 'Confirmed' else 'declined'}."
            )
            create_notification(
                cursor,
                booking["user_id"],
                "bookings",
                notification_title,
                notification_message,
                "/book-equipment.html",
            )
        connection.commit()
        send_email(
            booking["email"],
            f"{notification_title} - {equipment['resource_name']}",
            f"{notification_message}\n\nBooking reference: #{booking_id}",
        )
        return jsonify(message=message)
    except Exception:
        connection.rollback()
        raise


@dashboard_bp.get("/api/dashboard/user")
@api_route()
def api_user_dashboard(user):
    resources = resource_rows()
    mine = db.query_all(
        """
        SELECT request_id AS id, resource_name AS name, category, quantity,
               submitted_date AS submitted, needed_by, status, latest_update AS `update`
        FROM resource_request
        WHERE user_id = %s
        ORDER BY submitted_date DESC, request_id DESC
        """,
        (user["id"],),
    )
    open_requests = [r for r in mine if r["status"] in ("In review", "Approved", "Ready for collection")]
    waiting = sum(r["status"] == "In review" for r in mine)
    booking_rows = db.query_all(
        """
        SELECT b.booking_id AS id, r.resource_name AS equipment,
               b.booking_date AS `date`, b.start_time AS `start`, b.end_time AS `end`,
               b.room, b.purpose, b.status
        FROM equipment_booking AS b
        JOIN resource AS r ON r.resource_id = b.resource_id
        WHERE b.user_id = %s
          AND b.booking_date >= %s
          AND b.status != 'Declined'
        ORDER BY b.booking_date, b.start_time, b.booking_id
        """,
        (user["id"], today()),
    )
    bookings = [
        {
            **booking,
            "date": date_value(booking["date"]),
            "start": time_value(booking["start"]),
            "end": time_value(booking["end"]),
        }
        for booking in booking_rows
    ]
    loan_rows = db.query_all(
        """
        SELECT r.resource_name AS item,
               CAST(COALESCE(m.issued_quantity, m.quantity) - COALESCE(SUM(e.quantity), 0) AS SIGNED) AS quantity,
               m.movement_date AS issued, m.due_date AS due
        FROM item_movement AS m
        JOIN resource AS r ON r.resource_id = m.resource_id
        LEFT JOIN item_movement AS e
          ON e.related_issue_movement_id = m.movement_id
         AND e.movement_type IN ('return', 'lost', 'damaged')
        WHERE m.borrower_id = %s
          AND m.movement_type = 'issue'
          AND m.active_loan = TRUE
        GROUP BY m.movement_id, r.resource_name, m.issued_quantity, m.quantity,
                 m.movement_date, m.due_date
        HAVING quantity > 0
        ORDER BY m.due_date, m.movement_date, m.movement_id
        """,
        (user["school_id"],),
    )
    loans = [
        {
            **loan,
            "issued": date_value(loan["issued"]),
            "due": date_value(loan["due"]) if loan["due"] else None,
        }
        for loan in loan_rows
    ]
    due_soon = sum(loan_status(l)[0] != "On loan" for l in loans)
    next_booking = None
    if bookings:
        b = bookings[0]
        next_booking = {"equipment": b["equipment"], "date": b["date"], "start": b["start"], "end": b["end"], "room": b["room"],
                        "purpose": b["purpose"], "status": b["status"], "tone": BOOKING_TONES[b["status"]]}
    categories = []
    for name in ("Textbooks", "Stationery", "Equipment"):
        group = [i for i in resources if i["category"] == name]
        units = sum(i["stock"] for i in group)
        if units == 0:
            label, tone = "Out of stock", "danger"
        elif name == "Equipment":
            label, tone = "Bookable", "blue"
        elif any(i["stock"] <= i["reorder_level"] for i in group):
            label, tone = "Limited stock", "warning"
        else:
            label, tone = "In stock", "ok"
        categories.append({"category": name, "units": units, "label": label, "tone": tone})
    loan_rows = []
    for l in loans:
        label, tone = loan_status(l)
        loan_rows.append({"item": l["item"], "quantity": l["quantity"], "issued": l["issued"], "due": l["due"], "status": label, "tone": tone})
    available_resources = [i for i in resources if i["stock"] > 0]
    kpis = {
        "available_resources": {"value": sum(i["stock"] for i in resources), "note": f"Across {plural(len({i['category'] for i in available_resources}), 'category', 'categories')}"},
        "open_requests": {"value": len(open_requests), "note": f"{waiting} awaiting review"},
        "bookings": {"value": len(bookings), "note": f"Next: {date.fromisoformat(bookings[0]['date']).day} {date.fromisoformat(bookings[0]['date']).strftime('%B')}" if bookings else "No upcoming bookings"},
        "issued": {"value": sum(l["quantity"] for l in loans), "note": f"{plural(due_soon, 'return')} due soon" if due_soon else "Nothing due soon"},
    }
    return jsonify(kpis=kpis, categories=categories, loans=loan_rows, next_booking=next_booking)


@dashboard_bp.get("/api/dashboard/committee")
@api_route("ltsm")
def api_committee_dashboard(user):
    resources = resource_rows()
    low = sorted(
        (item for item in resources if stock_status(item)[0] != "In stock"),
        key=lambda item: item["stock"] / max(item["reorder_level"], 1),
    )
    pending = db.query_one(
        "SELECT COUNT(*) AS count FROM resource_request WHERE status = 'In review'"
    )["count"]
    submitted_today = db.query_one(
        "SELECT COUNT(*) AS count FROM resource_request WHERE status = 'In review' AND submitted_date = %s",
        (today(),),
    )["count"]
    upcoming = db.query_one(
        """
        SELECT COUNT(*) AS count FROM equipment_booking
        WHERE booking_date >= %s AND status != 'Declined'
        """,
        (today(),),
    )["count"]
    week_end = today() + timedelta(days=7)
    due_this_week = db.query_one(
        """
        SELECT COUNT(*) AS count FROM equipment_booking
        WHERE booking_date >= %s AND booking_date <= %s AND status != 'Declined'
        """,
        (today(), week_end),
    )["count"]
    kpis = {
        "inventory": {"value": sum(i["stock"] + i["reserved"] for i in resources), "note": f"Across {plural(len({i['category'] for i in resources}), 'category', 'categories')}"},
        "pending_requests": {"value": pending, "note": f"{submitted_today} submitted today"},
        "low_stock": {"value": len(low), "note": "Review replenishment" if low else "Stock levels are healthy"},
        "bookings": {"value": upcoming, "note": f"{due_this_week} due this week"},
    }
    return jsonify(kpis=kpis, low_stock=[{"id": i["id"], "name": i["name"], "stock": i["stock"], "tone": stock_status(i)[1]} for i in low])


def classify_abc_values(items):
    classifications = {}
    types = {item["inventory_type"] for item in items}
    for inventory_type in types:
        group = [item for item in items if item["inventory_type"] == inventory_type]
        valued = [item for item in group if item["abc_value"] is not None]
        total = sum(item["abc_value"] for item in valued)
        if total <= 0:
            for item in group:
                classifications[item["id"]] = "Unclassified"
            continue
        cumulative = 0.0
        for item in sorted(valued, key=lambda value: (-value["abc_value"], value["id"])):
            share_before = cumulative / total
            if item["abc_value"] <= 0:
                classification = "C"
            elif share_before < 0.80:
                classification = "A"
            elif share_before < 0.95:
                classification = "B"
            else:
                classification = "C"
            classifications[item["id"]] = classification
            cumulative += item["abc_value"]
        for item in group:
            if item["abc_value"] is None:
                classifications[item["id"]] = "Unclassified"
    return classifications


def annual_usage_value(forecast_item):
    annual_quantity = annual_usage_quantity(forecast_item)
    return round(annual_quantity * forecast_item["unit_price"], 2)


def annual_usage_quantity(forecast_item):
    annual_quantity = forecast_item["average"] * (
        12 if forecast_item["policy"] == "six_month" else 1
    )
    return round(annual_quantity, 2)


def annual_usage_abc_value(inventory_type, forecast_item, issued_quantity):
    if inventory_type == "consumable":
        return annual_usage_quantity(forecast_item) if forecast_item is not None else None
    if inventory_type == "non_consumable":
        return issued_quantity
    return None


def potential_excess_stock_value(resources, forecast):
    forecast_by_id = {int(item_id): value for item_id, value in forecast.items()}
    assessed_count = 0
    consumable_count = 0
    excess_value = 0.0
    for resource in resources:
        if resource["inventory_type"] != "consumable":
            continue
        consumable_count += 1
        result = forecast_by_id.get(resource["id"])
        if result is None:
            continue
        assessed_count += 1
        target_quantity = math.ceil(result["S"])
        excess_quantity = max(0, resource["on_hand"] - target_quantity)
        excess_value += excess_quantity * result["unit_price"]
    return round(excess_value, 2), assessed_count, consumable_count


@dashboard_bp.get("/api/dashboard/business-value")
@api_route("ltsm")
def api_committee_business_value(user):
    abc_basis_mode = request.args.get("basis", "value")
    if abc_basis_mode not in ("value", "usage"):
        raise ApiError("Choose value or annual usage for ABC classification.")

    resources = resource_rows()
    warnings = []
    forecast = inventory_model_live.calculate_from_database(db.get_db(), warnings=warnings)
    forecast_by_id = {int(item_id): value for item_id, value in forecast.items()}
    issue_quantities = {}
    if abc_basis_mode == "usage":
        issue_rows = db.query_all(
            """
            SELECT resource_id, SUM(COALESCE(issued_quantity, quantity)) AS quantity
            FROM item_movement
            WHERE movement_type = 'issue'
              AND movement_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
              AND movement_date <= CURDATE()
            GROUP BY resource_id
            """
        )
        issue_quantities = {
            row["resource_id"]: float(row["quantity"])
            for row in issue_rows
        }
    valued_items = []
    inventory_value = 0.0
    unpriced_count = 0

    for resource in resources:
        price = float(resource["unit_price"]) if resource["unit_price"] is not None else None
        on_hand_value = price * resource["on_hand"] if price is not None else None
        if on_hand_value is None:
            unpriced_count += 1
        else:
            inventory_value += on_hand_value

        forecast_item = forecast_by_id.get(resource["id"])
        if abc_basis_mode == "value":
            abc_value = None
            if resource["inventory_type"] == "consumable" and forecast_item is not None:
                abc_value = annual_usage_value(forecast_item)
                abc_basis = "Annual usage value"
            elif resource["inventory_type"] == "non_consumable":
                abc_value = on_hand_value
                abc_basis = "On-hand value" if on_hand_value is not None else "Needs unit price"
            elif resource["inventory_type"] == "consumable":
                abc_basis = "Needs price/forecast history"
            else:
                abc_basis = "Item type not set"
        else:
            abc_value = annual_usage_abc_value(
                resource["inventory_type"],
                forecast_item,
                issue_quantities.get(resource["id"]),
            )
            if resource["inventory_type"] == "consumable" and abc_value is not None:
                abc_basis = "Forecast annual usage"
            elif resource["inventory_type"] == "non_consumable":
                abc_basis = (
                    "Units issued in last 12 months"
                    if abc_value is not None else "No recorded issue history"
                )
            elif resource["inventory_type"] == "consumable":
                abc_basis = "Needs forecast history"
            else:
                abc_basis = "Item type not set"
        valued_items.append({
            **resource,
            "abc_value": abc_value,
            "abc_basis": abc_basis,
        })

    classes = classify_abc_values(valued_items)
    class_counts = {label: 0 for label in ("A", "B", "C", "Unclassified")}
    type_class_counts = {
        inventory_type: {label: 0 for label in ("A", "B", "C", "Unclassified")}
        for inventory_type in ("consumable", "non_consumable")
    }
    for item in valued_items:
        item["abc_class"] = classes[item["id"]]
        class_counts[item["abc_class"]] += 1
        if item["inventory_type"] in type_class_counts:
            type_class_counts[item["inventory_type"]][item["abc_class"]] += 1

    a_class_risks = [
        {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "inventory_type": item["inventory_type"],
            "abc_value": round(item["abc_value"], 2),
            "stock": item["stock"],
            "unit": item["unit"],
            "reorder_level": item["reorder_level"],
            "status": stock_status(item)[0],
        }
        for item in valued_items
        if item["abc_class"] == "A" and stock_status(item)[0] != "In stock"
    ]
    a_class_risks.sort(key=lambda item: (-item["abc_value"], item["name"]))
    abc_items = [
        {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "inventory_type": item["inventory_type"],
            "abc_class": item["abc_class"],
            "abc_value": round(item["abc_value"], 2) if item["abc_value"] is not None else None,
            "abc_basis": item["abc_basis"],
            "stock": item["stock"],
            "unit": item["unit"],
        }
        for item in valued_items
    ]
    class_order = {"A": 0, "B": 1, "C": 2, "Unclassified": 3}
    abc_items.sort(key=lambda item: (
        class_order[item["abc_class"]],
        -(item["abc_value"] or 0),
        item["name"].casefold(),
    ))

    return jsonify(
        inventory_value=round(inventory_value, 2),
        priced_item_count=len(resources) - unpriced_count,
        unpriced_item_count=unpriced_count,
        forecast_order_cost=round(sum(item["cost"] for item in forecast.values()), 2),
        forecast_item_count=len(forecast),
        forecast_warning_count=len(warnings),
        a_class_risk_count=len(a_class_risks),
        class_counts=class_counts,
        type_class_counts=type_class_counts,
        unclassified_count=class_counts["Unclassified"],
        a_class_risks=a_class_risks[:8],
        abc_basis_mode=abc_basis_mode,
        abc_items=abc_items,
    )


def parse_report_date(value, label, default):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else default
    except ValueError as error:
        raise ApiError(f"{label} must be a valid date.") from error


def average_or_none(values):
    return round(sum(values) / len(values), 2) if values else None


def percentage(numerator, denominator):
    return round(numerator * 100 / denominator, 2) if denominator else None


def evidence_change(baseline, current, direction):
    if baseline is None or current is None or baseline < 0:
        return None
    if baseline == 0:
        return 0.0 if current == 0 else None
    difference = current - baseline if direction == "higher" else baseline - current
    return round(difference * 100 / baseline, 1)


def manual_period_value(value, complete, has_observations):
    return value if complete or has_observations else None


def illustrative_demo_comparisons(baseline_rows, event_rows):
    baselines = {row["metric_key"]: row for row in baseline_rows}
    definitions = {metric["key"]: metric for metric in EVIDENCE_METRICS}
    demo_items = []

    for metric_key, event_key in (
        ("inventory_accuracy", "inventory_count"),
        ("report_preparation", "report_preparation"),
    ):
        baseline = baselines.get(metric_key)
        observations = [row for row in event_rows if row["metric_key"] == event_key]
        if not baseline or not observations:
            continue

        demo_dates = [date_value(row["occurred_at"])[:10] for row in observations]
        demo_start, demo_end = min(demo_dates), max(demo_dates)
        baseline_end = date_value(baseline["period_end"])
        if baseline_end >= demo_start:
            continue

        if metric_key == "inventory_accuracy":
            valid_counts = [
                row for row in observations
                if row["expected_quantity"] is not None
                and row["actual_quantity"] is not None
            ]
            current_value = percentage(
                sum(row["expected_quantity"] == row["actual_quantity"] for row in valid_counts),
                len(valid_counts),
            )
            sample_count = len(valid_counts)
        else:
            durations = [
                float(row["duration_minutes"])
                for row in observations
                if row["duration_minutes"] is not None
            ]
            current_value = average_or_none(durations)
            sample_count = len(durations)

        if current_value is None or sample_count == 0:
            continue
        demo_items.append({
            "key": metric_key,
            "label": definitions[metric_key]["label"],
            "unit": definitions[metric_key]["unit"],
            "baseline_value": float(baseline["measure_value"]),
            "baseline_sample_count": baseline["sample_count"],
            "baseline_start": date_value(baseline["period_start"]),
            "baseline_end": baseline_end,
            "current_value": current_value,
            "current_period_start": demo_start,
            "current_period_end": demo_end,
            "sample_count": sample_count,
            "illustrative": True,
        })

    return demo_items


def evidence_timed_values(column, start, end, extra_where="", from_column="submitted_at"):
    rows = db.query_all(
        f"""
        SELECT TIMESTAMPDIFF(MICROSECOND, {from_column}, {column}) / 60000000 AS minutes
        FROM resource_request
        WHERE {column} IS NOT NULL AND {from_column} IS NOT NULL
          AND {column} >= %s
          AND {column} < DATE_ADD(%s, INTERVAL 1 DAY) {extra_where}
        """,
        (start, end),
    )
    return [float(row["minutes"]) for row in rows]


def evidence_period_values(start, end):
    requests_count = db.query_one(
        """
        SELECT COUNT(*) AS count FROM resource_request
        WHERE submitted_at >= %s AND submitted_at < DATE_ADD(%s, INTERVAL 1 DAY)
        """,
        (start, end),
    )["count"]
    booking_count = db.query_one(
        """
        SELECT COUNT(*) AS count FROM equipment_booking
        WHERE requested_at >= %s AND requested_at < DATE_ADD(%s, INTERVAL 1 DAY)
        """,
        (start, end),
    )["count"]
    conflict_count = db.query_one(
        """
        SELECT COUNT(*) AS count FROM operational_measurement
        WHERE metric_key = 'booking_conflict' AND is_demo = FALSE
          AND occurred_at >= %s AND occurred_at < DATE_ADD(%s, INTERVAL 1 DAY)
        """,
        (start, end),
    )["count"]
    ready_minutes = evidence_timed_values("ready_at", start, end)
    collection_minutes = evidence_timed_values(
        "fulfilled_at", start, end, "AND ready_at IS NOT NULL", "ready_at"
    )
    fulfillment_minutes = evidence_timed_values("fulfilled_at", start, end)
    attempts = booking_count + conflict_count
    return {
        "requests_submitted": (requests_count, requests_count),
        "request_waiting": (average_or_none(ready_minutes), len(ready_minutes)),
        "collection_waiting": (average_or_none(collection_minutes), len(collection_minutes)),
        "request_fulfillment": (average_or_none(fulfillment_minutes), len(fulfillment_minutes)),
        "bookings_requested": (booking_count, booking_count),
        "booking_conflicts": (
            percentage(conflict_count, attempts) if attempts else None,
            attempts,
        ),
    }


def automatic_evidence_change(previous, current, kind):
    if previous is None or current is None:
        return None
    if kind == "count":
        return round(current - previous, 2)
    if previous == 0:
        return 0.0 if current == 0 else None
    return round((current - previous) * 100 / abs(previous), 1)


def evidence_daily_trend(metric_key, start, end):
    if metric_key in ("requests_submitted", "bookings_requested"):
        table, timestamp = (
            ("resource_request", "submitted_at")
            if metric_key == "requests_submitted"
            else ("equipment_booking", "requested_at")
        )
        rows = db.query_all(
            f"""
            SELECT DATE({timestamp}) AS event_date, COUNT(*) AS value,
                   COUNT(*) AS sample_count
            FROM {table}
            WHERE {timestamp} >= %s AND {timestamp} < DATE_ADD(%s, INTERVAL 1 DAY)
            GROUP BY DATE({timestamp})
            ORDER BY event_date
            """,
            (start, end),
        )
        return [
            {
                "date": date_value(row["event_date"]),
                "value": int(row["value"]),
                "sample_count": int(row["sample_count"]),
            }
            for row in rows
        ]

    if metric_key == "booking_conflicts":
        rows = db.query_all(
            """
            SELECT DATE(attempts.occurred_at) AS event_date,
                   SUM(attempts.is_conflict) AS conflicts,
                   COUNT(*) AS attempts
            FROM (
                SELECT requested_at AS occurred_at, 0 AS is_conflict
                FROM equipment_booking
                WHERE requested_at >= %s AND requested_at < DATE_ADD(%s, INTERVAL 1 DAY)
                UNION ALL
                SELECT occurred_at, 1 AS is_conflict
                FROM operational_measurement
                WHERE metric_key = 'booking_conflict' AND is_demo = FALSE
                  AND occurred_at >= %s AND occurred_at < DATE_ADD(%s, INTERVAL 1 DAY)
            ) AS attempts
            GROUP BY DATE(attempts.occurred_at)
            ORDER BY event_date
            """,
            (start, end, start, end),
        )
        return [
            {
                "date": date_value(row["event_date"]),
                "value": percentage(row["conflicts"], row["attempts"]),
                "sample_count": int(row["attempts"]),
            }
            for row in rows
        ]

    timing_columns = {
        "request_waiting": ("ready_at", "submitted_at", ""),
        "collection_waiting": ("fulfilled_at", "ready_at", "AND ready_at IS NOT NULL"),
        "request_fulfillment": ("fulfilled_at", "submitted_at", ""),
    }
    column, from_column, extra_where = timing_columns[metric_key]
    rows = db.query_all(
        f"""
        SELECT DATE({column}) AS event_date,
               AVG(TIMESTAMPDIFF(MICROSECOND, {from_column}, {column}) / 60000000) AS value,
               COUNT(*) AS sample_count
        FROM resource_request
        WHERE {column} IS NOT NULL AND {from_column} IS NOT NULL
          AND {column} >= %s AND {column} < DATE_ADD(%s, INTERVAL 1 DAY)
          {extra_where}
        GROUP BY DATE({column})
        ORDER BY event_date
        """,
        (start, end),
    )
    return [
        {
            "date": date_value(row["event_date"]),
            "value": round(float(row["value"]), 2),
            "sample_count": int(row["sample_count"]),
        }
        for row in rows
    ]


@evidence_bp.get("/api/evidence/automatic")
@api_route("ltsm")
def api_automatic_evidence(user):
    end = parse_report_date(request.args.get("to"), "End date", today())
    start = parse_report_date(request.args.get("from"), "Start date", end - timedelta(days=29))
    if start > end:
        raise ApiError("Start date must be on or before end date.")

    period_length = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_length - 1)
    current_values = evidence_period_values(start, end)
    previous_values = evidence_period_values(previous_start, previous_end)
    items = []
    for metric in AUTOMATIC_EVIDENCE_METRICS:
        current_value, current_samples = current_values[metric["key"]]
        previous_value, previous_samples = previous_values[metric["key"]]
        change = automatic_evidence_change(
            previous_value, current_value, metric["kind"]
        )
        items.append({
            **metric,
            "current_value": current_value,
            "current_sample_count": current_samples,
            "previous_value": previous_value,
            "previous_sample_count": previous_samples,
            "change": change,
        })

    return jsonify(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        previous_period_start=previous_start.isoformat(),
        previous_period_end=previous_end.isoformat(),
        items=items,
    )


@evidence_bp.get("/api/evidence/trends")
@api_route("ltsm")
def api_evidence_trends(user):
    metric_key = request.args.get("metric", "")
    metric = next(
        (item for item in AUTOMATIC_EVIDENCE_METRICS if item["key"] == metric_key),
        None,
    )
    if metric is None:
        raise ApiError("Choose a supported automatic KPI.")

    end = parse_report_date(request.args.get("to"), "End date", today())
    start = parse_report_date(request.args.get("from"), "Start date", end - timedelta(days=29))
    if start > end:
        raise ApiError("Start date must be on or before end date.")
    points = evidence_daily_trend(metric_key, start, end)
    return jsonify(
        key=metric_key,
        label=metric["label"],
        unit=metric["unit"],
        kind=metric["kind"],
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        sample_count=sum(point["sample_count"] for point in points),
        points=points,
    )


@evidence_bp.get("/api/evidence")
@api_route("ltsm")
def api_evidence(user):
    end = parse_report_date(request.args.get("to"), "End date", today())
    start = parse_report_date(request.args.get("from"), "Start date", end - timedelta(days=29))
    if start > end:
        raise ApiError("Start date must be on or before end date.")

    requests_count = db.query_one(
        """
        SELECT COUNT(*) AS count FROM resource_request
        WHERE submitted_at >= %s AND submitted_at < DATE_ADD(%s, INTERVAL 1 DAY)
        """,
        (start, end),
    )["count"]
    ready_minutes = evidence_timed_values("ready_at", start, end)
    collection_minutes = evidence_timed_values(
        "fulfilled_at", start, end, "AND ready_at IS NOT NULL", "ready_at"
    )
    fulfillment_minutes = evidence_timed_values("fulfilled_at", start, end)
    event_rows = db.query_all(
        """
        SELECT metric_key, occurred_at, ended_at, duration_minutes,
               expected_quantity, actual_quantity
        FROM operational_measurement
        WHERE is_demo = FALSE
          AND occurred_at >= %s AND occurred_at < DATE_ADD(%s, INTERVAL 1 DAY)
        """,
        (start, end),
    )
    counts = Counter(row["metric_key"] for row in event_rows)
    total_booking_count = db.query_one(
        """
        SELECT COUNT(*) AS count FROM equipment_booking
        WHERE requested_at >= %s AND requested_at < DATE_ADD(%s, INTERVAL 1 DAY)
        """,
        (start, end),
    )["count"]
    conflict_count = counts["booking_conflict"]
    conflict_attempts = total_booking_count + conflict_count
    inventory_rows = [row for row in event_rows if row["metric_key"] == "inventory_count"]
    accurate_counts = sum(row["expected_quantity"] == row["actual_quantity"] for row in inventory_rows)
    prep_durations = [
        float(row["duration_minutes"])
        for row in event_rows
        if row["metric_key"] == "report_preparation" and row["duration_minutes"] is not None
    ]
    motion_durations = [
        float(row["duration_minutes"])
        for row in event_rows
        if row["metric_key"] == "motion_time" and row["duration_minutes"] is not None
    ]
    incorrect_count = counts["incorrect_fulfillment"]
    fulfilled_count = db.query_one(
        """
        SELECT COUNT(*) AS count FROM resource_request
        WHERE fulfilled_at >= %s AND fulfilled_at < DATE_ADD(%s, INTERVAL 1 DAY)
        """,
        (start, end),
    )["count"]

    downtime_rows = db.query_all(
        """
        SELECT occurred_at, ended_at
        FROM operational_measurement
        WHERE is_demo = FALSE
          AND metric_key = 'equipment_downtime'
          AND occurred_at < DATE_ADD(%s, INTERVAL 1 DAY)
          AND (ended_at IS NULL OR ended_at > %s)
        """,
        (end, start),
    )
    period_start = datetime.combine(start, datetime.min.time())
    period_end = datetime.combine(end + timedelta(days=1), datetime.min.time())
    downtime_minutes = 0.0
    for row in downtime_rows:
        outage_start = max(row["occurred_at"], period_start)
        outage_end = min(row["ended_at"] or now().replace(tzinfo=None), period_end)
        if outage_end > outage_start:
            downtime_minutes += (outage_end - outage_start).total_seconds() / 60

    consumable_resources = [
        resource for resource in resource_rows()
        if resource["inventory_type"] == "consumable"
    ]
    forecast_warnings = []
    forecast = inventory_model_live.calculate_from_database(
        db.get_db(), warnings=forecast_warnings
    )
    excess_value, excess_assessed_count, excess_total_count = potential_excess_stock_value(
        consumable_resources, forecast
    )

    request_denominator = requests_count
    live = {
        "request_waiting": (average_or_none(ready_minutes), len(ready_minutes)),
        "collection_waiting": (average_or_none(collection_minutes), len(collection_minutes)),
        "request_fulfillment": (average_or_none(fulfillment_minutes), len(fulfillment_minutes)),
        "unnecessary_trips": (
            percentage(counts["unnecessary_trip"], request_denominator),
            request_denominator,
        ),
        "follow_up_enquiries": (
            percentage(counts["follow_up_enquiry"], request_denominator),
            request_denominator,
        ),
        "inventory_accuracy": (
            percentage(accurate_counts, len(inventory_rows)),
            len(inventory_rows),
        ),
        "potential_excess_stock": (
            excess_value if excess_assessed_count else None,
            excess_assessed_count,
        ),
        "booking_conflicts": (
            percentage(conflict_count, conflict_attempts),
            conflict_attempts,
        ),
        "report_preparation": (average_or_none(prep_durations), len(prep_durations)),
        "motion_time": (round(sum(motion_durations), 2), len(motion_durations)),
        "incorrect_fulfillment": (
            percentage(incorrect_count, fulfilled_count),
            fulfilled_count,
        ),
        "equipment_downtime": (
            round(downtime_minutes / 60, 2), len(downtime_rows),
        ),
    }
    baseline_rows = db.query_all(
        """
        SELECT metric_key, period_start, period_end, measure_value, sample_count
        FROM evidence_baseline
        WHERE is_demo = FALSE
        """
    )
    completion_rows = db.query_all(
        """
        SELECT metric_key FROM evidence_period_completion
        WHERE is_demo = FALSE
          AND period_start = %s AND period_end = %s
        """,
        (start, end),
    )
    completed_manual_keys = {row["metric_key"] for row in completion_rows}
    baselines = {row["metric_key"]: row for row in baseline_rows}
    snapshot_date = today()
    items = []
    for definition in EVIDENCE_METRICS:
        current_value, sample_count = live[definition["key"]]
        baseline = baselines.get(definition["key"])
        baseline_value = float(baseline["measure_value"]) if baseline else None
        comparison_date = snapshot_date if definition.get("snapshot") else start
        baseline_is_before_period = baseline and baseline["period_end"] < comparison_date
        manual_complete = (
            not definition.get("manual") or definition.get("snapshot")
            or definition["key"] in completed_manual_keys
        )
        if definition.get("manual") and not manual_complete:
            has_manual_observations = {
                "unnecessary_trips": counts["unnecessary_trip"] > 0,
                "follow_up_enquiries": counts["follow_up_enquiry"] > 0,
                "inventory_accuracy": bool(inventory_rows),
                "report_preparation": bool(prep_durations),
                "motion_time": bool(motion_durations),
                "incorrect_fulfillment": incorrect_count > 0,
                "equipment_downtime": bool(downtime_rows),
            }[definition["key"]]
            current_value = manual_period_value(
                current_value, manual_complete, has_manual_observations
            )
        change = (
            evidence_change(baseline_value, current_value, definition["direction"])
            if baseline_is_before_period and manual_complete else None
        )
        comparison_note = None
        if definition.get("manual") and not manual_complete:
            comparison_note = "Manual records are not marked complete for this period."
        elif definition.get("snapshot"):
            comparison_note = (
                f"Current value is a live snapshot as of {snapshot_date.isoformat()}, "
                "not a selected-period total."
            )
            if baseline and not baseline_is_before_period:
                comparison_note += " Baseline must end before the snapshot date."
        elif baseline and not baseline_is_before_period:
            comparison_note = "Baseline must end before the portal period starts."
        items.append({
            **definition,
            "current_value": current_value,
            "sample_count": sample_count,
            "coverage_count": (
                excess_total_count if definition["key"] == "potential_excess_stock" else None
            ),
            "baseline_value": baseline_value,
            "baseline_sample_count": baseline["sample_count"] if baseline else None,
            "baseline_start": date_value(baseline["period_start"]) if baseline else None,
            "baseline_end": date_value(baseline["period_end"]) if baseline else None,
            "change_percent": change,
            "manual_complete": manual_complete,
            "snapshot_date": snapshot_date.isoformat() if definition.get("snapshot") else None,
            "comparison_note": comparison_note,
        })

    demo_baseline_rows = db.query_all(
        """
        SELECT metric_key, period_start, period_end, measure_value, sample_count
        FROM evidence_baseline
        WHERE is_demo = TRUE AND metric_key IN (%s, %s)
        """,
        ("inventory_accuracy", "report_preparation"),
    )
    demo_event_rows = db.query_all(
        """
        SELECT metric_key, occurred_at, duration_minutes,
               expected_quantity, actual_quantity
        FROM operational_measurement
        WHERE is_demo = TRUE AND metric_key IN (%s, %s)
        """,
        ("inventory_count", "report_preparation"),
    )
    demo_items = illustrative_demo_comparisons(
        demo_baseline_rows, demo_event_rows
    )

    return jsonify(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        snapshot_date=snapshot_date.isoformat(),
        request_count=request_denominator,
        items=items,
        illustrative_demo_items=demo_items,
    )


@evidence_bp.post("/api/evidence/baseline")
@api_route("ltsm")
def api_save_evidence_baseline(user):
    v = Validator(json_body())
    period_start = v.day("period_start", "Baseline start date")
    period_end = v.day("period_end", "Baseline end date")
    rows = v.data.get("items")
    if not isinstance(rows, list) or not rows:
        v._fail("items", "Enter at least one baseline measurement.")
        rows = []
    validated = []
    known_metrics = {metric["key"]: metric for metric in EVIDENCE_METRICS}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            v._fail("items", "Each baseline measurement must be an object.")
            continue
        metric_key = row.get("metric_key")
        if metric_key not in known_metrics:
            v._fail("items", "Choose a supported baseline measurement.")
            continue
        maximum = 100 if known_metrics[metric_key]["unit"] == "percent" else 1000000000
        value = Validator(row)
        measure_value = value.decimal("value", "Baseline value", 0, maximum)
        sample_count = value.integer("sample_count", "Sample count", 1, 1000000000)
        if value.errors:
            v._fail("items", f"Check baseline row {index + 1}: {' '.join(value.errors.values())}")
        validated.append((metric_key, measure_value, sample_count))
    notes = v.text("notes", "Notes", 0, 500)
    if period_start and period_end and period_start > period_end:
        v._fail("period_end", "Baseline end date must be on or after its start date.")
    v.done()

    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            for metric_key, value, sample_count in validated:
                cursor.execute(
                    """
                    INSERT INTO evidence_baseline
                      (metric_key, period_start, period_end, measure_value,
                       sample_count, notes, recorded_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                      period_start = VALUES(period_start),
                      period_end = VALUES(period_end),
                      measure_value = VALUES(measure_value),
                      sample_count = VALUES(sample_count),
                      notes = VALUES(notes),
                      recorded_by_user_id = VALUES(recorded_by_user_id),
                      is_demo = FALSE
                    """,
                    (
                        metric_key, period_start, period_end, value,
                        sample_count, notes or None, user["id"],
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message=f"Saved {len(validated)} baseline measurement(s).")


@evidence_bp.post("/api/evidence/completion")
@api_route("ltsm")
def api_complete_evidence_period(user):
    v = Validator(json_body())
    period_start = v.day("period_start", "Period start")
    period_end = v.day("period_end", "Period end")
    if period_start and period_end and period_start > period_end:
        v._fail("period_end", "Period end must be on or after its start date.")
    v.done()

    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            for metric_key in MANUAL_EVIDENCE_KEYS:
                cursor.execute(
                    """
                    INSERT INTO evidence_period_completion
                      (metric_key, period_start, period_end, recorded_by_user_id)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                      completed_at = CURRENT_TIMESTAMP(6),
                      recorded_by_user_id = VALUES(recorded_by_user_id),
                      is_demo = FALSE
                    """,
                    (metric_key, period_start, period_end, user["id"]),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message="Manual records marked complete for this period.")


def optional_id(v, key, label):
    value = v.data.get(key)
    if value in (None, ""):
        return None
    return v.integer(key, label, 1, 2147483647)


@evidence_bp.post("/api/evidence/measurements")
@api_route("ltsm")
def api_record_evidence_measurement(user):
    v = Validator(json_body())
    metric_key = v.choice(
        "metric_key",
        "Measurement type",
        (
            "unnecessary_trip", "follow_up_enquiry", "incorrect_fulfillment",
            "report_preparation", "equipment_downtime", "inventory_count",
            "motion_time",
        ),
    )
    notes = v.text("notes", "Notes", 1, 500)
    request_id = optional_id(v, "request_id", "Request")
    resource_id = optional_id(v, "resource_id", "Inventory item")
    actual_quantity = None
    duration_minutes = None
    expected_quantity = None

    if metric_key == "report_preparation":
        duration_minutes = v.decimal("duration_minutes", "Preparation time", 0.01, 1440)
    elif metric_key == "motion_time":
        duration_minutes = v.decimal("duration_minutes", "Searching or moving time", 0.01, 1440)
    elif metric_key == "inventory_count":
        actual_quantity = v.integer("actual_quantity", "Counted quantity", 0, 1000000000)
        if not resource_id:
            v._fail("resource_id", "Choose the item that was physically counted.")
    elif metric_key == "equipment_downtime" and not resource_id:
        v._fail("resource_id", "Choose the equipment that is out of service.")

    v.done()
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            occurred_at = now().replace(tzinfo=None)
            if request_id:
                cursor.execute("SELECT request_id FROM resource_request WHERE request_id = %s", (request_id,))
                if cursor.fetchone() is None:
                    raise ApiError("That request does not exist.", 404)
            if resource_id:
                cursor.execute(
                    "SELECT resource_id, category, quantity_in_stock FROM resource WHERE resource_id = %s",
                    (resource_id,),
                )
                resource = cursor.fetchone()
                if resource is None:
                    raise ApiError("That inventory item does not exist.", 404)
                if metric_key == "equipment_downtime" and resource["category"] != "Equipment":
                    raise ApiError("Choose an equipment item for a downtime record.")
                if metric_key == "inventory_count":
                    expected_quantity = resource["quantity_in_stock"]
            cursor.execute(
                """
                INSERT INTO operational_measurement
                  (metric_key, occurred_at, duration_minutes, resource_id, request_id,
                   expected_quantity, actual_quantity, notes, recorded_by_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    metric_key, occurred_at, duration_minutes, resource_id, request_id,
                    expected_quantity, actual_quantity, notes, user["id"],
                ),
            )
            measurement_id = cursor.lastrowid
            evidence_metric_key = {
                "unnecessary_trip": "unnecessary_trips",
                "follow_up_enquiry": "follow_up_enquiries",
                "incorrect_fulfillment": "incorrect_fulfillment",
                "report_preparation": "report_preparation",
                "equipment_downtime": "equipment_downtime",
                "inventory_count": "inventory_accuracy",
                "motion_time": "motion_time",
            }[metric_key]
            cursor.execute(
                """
                DELETE FROM evidence_period_completion
                WHERE metric_key = %s AND period_start <= %s AND period_end >= %s
                """,
                (evidence_metric_key, occurred_at.date(), occurred_at.date()),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message="Measurement recorded.", id=measurement_id), 201


@evidence_bp.post("/api/evidence/downtime/<int:measurement_id>/restore")
@api_route("ltsm")
def api_restore_evidence_downtime(user, measurement_id):
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT occurred_at, ended_at FROM operational_measurement
                WHERE measurement_id = %s AND metric_key = 'equipment_downtime'
                FOR UPDATE
                """,
                (measurement_id,),
            )
            outage = cursor.fetchone()
            if outage is None:
                raise ApiError("That downtime record does not exist.", 404)
            if outage["ended_at"] is not None:
                raise ApiError("That equipment outage has already been closed.", 409)
            restored_at = now().replace(tzinfo=None)
            cursor.execute(
                """
                UPDATE operational_measurement SET ended_at = %s
                WHERE measurement_id = %s
                """,
                (restored_at, measurement_id),
            )
            cursor.execute(
                """
                DELETE FROM evidence_period_completion
                WHERE metric_key = 'equipment_downtime'
                  AND period_end >= %s AND period_start <= %s
                """,
                (outage["occurred_at"].date(), restored_at.date()),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(message="Equipment marked back in service.")


@evidence_bp.get("/api/evidence/open-downtime")
@api_route("ltsm")
def api_open_evidence_downtime(user):
    rows = db.query_all(
        """
        SELECT om.measurement_id AS id, r.resource_name AS item, om.occurred_at AS started
        FROM operational_measurement AS om
        JOIN resource AS r ON r.resource_id = om.resource_id
        WHERE om.metric_key = 'equipment_downtime'
          AND om.is_demo = FALSE AND om.ended_at IS NULL
        ORDER BY om.occurred_at
        """
    )
    return jsonify(items=[
        {**row, "started": datetime_value(row["started"])}
        for row in rows
    ])


def join_phrases(parts):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


@reports_bp.get("/api/reports")
@api_route("ltsm")
def api_reports(user):
    resources = resource_rows()
    movement_rows = db.query_all(
        """
        SELECT m.resource_id,
               CAST(SUM(COALESCE(m.issued_quantity, m.quantity) - COALESCE(e.resolved, 0)) AS SIGNED) AS quantity
        FROM item_movement AS m
        LEFT JOIN (
            SELECT related_issue_movement_id, SUM(quantity) AS resolved
            FROM item_movement
            WHERE movement_type IN ('return', 'lost', 'damaged')
              AND related_issue_movement_id IS NOT NULL
            GROUP BY related_issue_movement_id
        ) AS e ON e.related_issue_movement_id = m.movement_id
        WHERE m.movement_type = 'issue' AND m.active_loan = TRUE
        GROUP BY m.resource_id
        """
    )
    out = Counter({row["resource_id"]: row["quantity"] for row in movement_rows})
    available = sum(i["stock"] for i in resources)
    reserved = sum(i["reserved"] for i in resources)
    on_loan = sum(out.values())
    total = available + reserved + on_loan
    low = [i for i in resources if stock_status(i)[0] != "In stock"]
    low_by_category = Counter(i["category"] for i in low)
    request_rows = db.query_all(
        "SELECT status, COUNT(*) AS count FROM resource_request GROUP BY status"
    )
    counts = Counter({row["status"]: row["count"] for row in request_rows})
    approved = counts["Approved"] + counts["Ready for collection"]

    stock_finding = (f"{available:,} of {total:,} units are available ({available / total * 100:.1f}%); {on_loan:,} are currently on loan."
                     if total else "No inventory has been recorded yet.")
    low_finding = (f"{plural(len(low), 'item')} {'is' if len(low) == 1 else 'are'} low: "
                   + join_phrases([plural(n, f"{CATEGORY_WORD[c]} item") for c, n in low_by_category.items()]) + "."
                   if low else "No items are below their reorder level.")
    summary = [
        {"area": "Stock availability", "finding": stock_finding, "action": "Monitor unavailable stock and prioritize replenishment where demand is highest."},
        {"area": "Low-stock categories", "finding": low_finding, "action": "Review stationery and textbook reorder levels before the next distribution period."},
        {"area": "Requests awaiting review", "finding": f"{plural(counts['In review'], 'request')} {'is' if counts['In review'] == 1 else 'are'} in review; {approved} approved and {counts['Declined']} declined.",
         "action": "Review the pending queue and update request statuses."},
    ]
    categories = []
    for name in CATEGORIES:
        group = [i for i in resources if i["category"] == name]
        if not group:
            continue
        units = sum(i["stock"] for i in group)
        n_low = low_by_category[name]
        categories.append({"category": name, "total": units + sum(i["reserved"] for i in group) + sum(out[i["id"]] for i in group), "available": units, "low_stock": n_low,
                           "condition": "Review stock" if n_low else "Healthy", "tone": "warning" if n_low else "ok"})
    statuses = [{"status": s, "count": counts[s], "tone": REQUEST_TONES[s]} for s in ("Approved", "Ready for collection", "In review", "Declined", "Fulfilled")]
    return jsonify(summary=summary, categories=categories, requests_by_status=statuses)


@health_bp.get("/health")
def health():
    """Used by hosting platforms and the runbook to check that the app is up."""
    return jsonify(status="ok", time=now().isoformat(timespec="seconds"))


for blueprint in BLUEPRINTS:
    app.register_blueprint(blueprint)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=app.config["DEBUG"],
    )
