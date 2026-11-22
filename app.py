"""
LTSM Portal – Flask application (Task 3A).

Serves the Jinja templates in Templates/ and the JSON API under /api that the
fetch() code in static/js/ calls. See API_CONTRACT.md for every endpoint.

Run:  python app.py   then open http://127.0.0.1:5000
"""
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, session
import db
import model
import inventory_model_live

try:  # optional: load settings from a local .env file (see .env.example)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

APP_ENV = os.environ.get("APP_ENV", "development")
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Africa/Johannesburg")

app = Flask(__name__, template_folder="Templates", static_folder="static")
db.init_app(app)
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    if APP_ENV == "production":
        raise RuntimeError("SECRET_KEY must be set when APP_ENV=production (see .env.example).")
    _secret = "dev-only-change-me"
app.secret_key = _secret
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=(APP_ENV == "production"))

def now():
    """Current time in the school's timezone (servers usually run in UTC, which is 2 hours behind South Africa)."""
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def today():
    return now().date()


CATEGORIES = ["Textbooks", "Stationery", "Equipment", "Other"]
CATEGORY_WORD = {"Textbooks": "textbook", "Stationery": "stationery", "Equipment": "equipment", "Other": "other"}
REQUEST_TONES = {"In review": "warning", "Approved": "ok", "Ready for collection": "blue", "Declined": "danger"}
BOOKING_TONES = {"Confirmed": "ok", "Awaiting approval": "warning", "Declined": "danger"}
MAINTENANCE_TONES = {"Open": "warning", "In repair": "warning", "Out of service": "danger", "Resolved": "ok"}


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
    return model.get_user_by_id(user_id) if user_id is not None else None


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
               COALESCE(description, '') AS description, category,
               quantity_in_stock AS stock, reorder_level,
               unit_of_measure AS unit
        FROM resource
        ORDER BY resource_name, grade, resource_id
        """
    )


def date_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def time_value(value):
    return value.strftime("%H:%M") if hasattr(value, "strftime") else str(value)[:5]


def matches(item, query, category):
    haystack = f"{item['name']} {item['description']} {item['category']}".lower()
    return query.lower() in haystack and (not category or item["category"] == category)


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
COMMITTEE_PAGES = {"ltsm-dashboard", "manage-inventory", "issue-return", "maintenance", "reports", "manage-users", "inventory-summary"}


def dashboard_for(user):
    return "/ltsm-dashboard.html" if user["role"] == "ltsm" else "/user-dashboard.html"


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/login")
def login():
    return render_template("login.html")


@app.get("/register")
def register():
    return render_template("register.html")


@app.get("/<page>.html")
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


# --------------------------------------------------------------------------- #
# API: accounts
# --------------------------------------------------------------------------- #
@app.post("/api/login")
def api_login():
    data = json_body()
    username = str(data.get("username", "")).strip().lower()
    user = model.authenticate_user(
        username,
        str(data.get("password", "")),
        data.get("role"),
    )
    if user is None:
        raise ApiError("Incorrect role, username or password.", 401)  # one message so accounts cannot be probed
    session.clear()
    session["uid"] = user["id"]
    return jsonify(user={"id": user["id"], "name": user["name"], "role": user["role"]}, redirect=dashboard_for(user))


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(redirect="/login")


@app.post("/api/register")
def api_register():
    data = json_body()
    v = Validator(data)
    name = v.text("full_name", "Full name", 2, 100)
    role = v.choice("account_type", "Account type", ("learner", "teacher"))
    school_id = v.text("school_id", "Student / staff number", 1, 40)
    email = v.email("email", "Email address")
    password = data.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        v._fail("password", "Password must be 8–128 characters.")
    elif data.get("confirm_password") != password:
        v._fail("confirm_password", "Passwords do not match.")
    v.done()
    try:
        model.create_user(name, school_id, email, password, role)
    except model.UserAlreadyExistsError as error:
        field = error.field
        label = "email address" if field == "email" else "student / staff number"
        raise ApiError(
            f"An account with that {label} already exists.",
            409,
            {field: "Already registered."},
        ) from error
    return jsonify(message="Account created."), 201


@app.get("/api/committee/users")
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
            "is_current_user": row["user_id"] == user["id"],
        }
        for row in users
    ])


@app.post("/api/committee/users")
@api_route("ltsm")
def api_committee_create_user(user):
    data = json_body()
    validator = Validator(data)
    name = validator.text("full_name", "Full name", 2, 100)
    role = validator.choice("role", "Role", ("learner", "staff", "ltsm"))
    school_id = validator.text("school_id", "Student / staff number", 1, 40)
    email = validator.email("email", "Email address")
    password = data.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        validator._fail("password", "Password must be 8–128 characters.")
    validator.done()
    try:
        new_user_id = model.create_user(name, school_id, email, password, role)
    except model.UserAlreadyExistsError as error:
        field = error.field
        label = "email address" if field == "email" else "student / staff number"
        raise ApiError(
            f"An account with that {label} already exists.",
            409,
            {field: "Already registered."},
        ) from error
    return jsonify(message="User account created.", id=new_user_id), 201


@app.post("/api/committee/users/<int:user_id>/status")
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
# API: teacher / learner features
# --------------------------------------------------------------------------- #
@app.get("/api/resources")
@api_route()
def api_resources(user):
    query, category = request.args.get("q", "").strip(), request.args.get("category", "").strip()
    items = []
    for item in filter(lambda i: matches(i, query, category), resource_rows()):
        label, tone = availability(item)
        items.append({**{k: item[k] for k in ("id", "name", "description", "category", "stock", "unit")}, "availability": label, "tone": tone})
    return jsonify(items=items)


@app.post("/api/suggestions")
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


@app.post("/api/requests")
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
        SELECT resource_name AS name, category, quantity_in_stock AS stock,
               unit_of_measure AS unit
        FROM resource
        WHERE LOWER(TRIM(resource_name)) = LOWER(%s)
        LIMIT 1
        """,
        (row["name"],),
    )
    if inventory_item:
        if row["quantity"] > inventory_item["stock"]:
            raise ApiError(
                f"Only {inventory_item['stock']} {inventory_item['unit']} of {inventory_item['name']} are currently available.",
                409,
                {"quantity": "Requested quantity exceeds current availability."},
            )
        row["category"] = inventory_item["category"]
    request_id = db.execute(
        """
        INSERT INTO resource_request
          (user_id, resource_name, category, quantity, needed_by, purpose,
           submitted_date, status, latest_update)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'In review', 'Committee review in progress')
        """,
        (
            user["id"], row["name"], row["category"], row["quantity"],
            row["needed_by"], row["purpose"], today(),
        ),
    )
    return jsonify(message="Request submitted.", id=request_id), 201


@app.get("/api/requests")
@api_route()
def api_my_requests(user):
    status = request.args.get("status", "").strip()
    sql = """
        SELECT request_id AS id, resource_name AS name, category,
               submitted_date AS submitted, quantity, needed_by, status,
               latest_update AS `update`
        FROM resource_request
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
            "tone": REQUEST_TONES[row["status"]],
        }
        for row in rows
    ])


@app.get("/api/equipment")
@api_route()
def api_equipment(user):
    return jsonify(items=[
        {"id": item["id"], "name": item["name"], "stock": item["stock"]}
        for item in resource_rows()
        if item["category"] == "Equipment"
    ])


@app.post("/api/bookings")
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
    item = db.query_one(
        """
        SELECT resource_id AS id, resource_name AS name, category,
               quantity_in_stock AS stock
        FROM resource
        WHERE resource_id = %s
        """,
        (equipment_id,),
    )
    if not item or item["category"] != "Equipment":
        raise ApiError("Choose equipment from the list.", 400, {"equipment_id": "Unknown equipment."})
    overlapping = db.query_one(
        """
        SELECT COUNT(*) AS booking_count
        FROM equipment_booking
        WHERE resource_id = %s AND booking_date = %s
          AND status != 'Declined'
          AND start_time < %s AND end_time > %s
        """,
        (item["id"], day, end, start),
    )["booking_count"]
    if overlapping >= item["stock"]:
        raise ApiError(f"No {item['name']} is free on {day.isoformat()} between {start} and {end}. Try another time.", 409)
    booking_id = db.execute(
        """
        INSERT INTO equipment_booking
          (user_id, resource_id, booking_date, start_time, end_time,
           room, purpose, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Awaiting approval')
        """,
        (user["id"], item["id"], day, start, end, room, purpose),
    )
    return jsonify(message=f"Booking requested: {item['name']} on {day.isoformat()}, {start}–{end}. The LTSM committee will confirm it."), 201


@app.get("/api/bookings")
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
@app.get("/api/inventory")
@api_route("ltsm")
def api_inventory(user):
    query, category = request.args.get("q", "").strip(), request.args.get("category", "").strip()
    items = []
    for item in filter(lambda i: matches(i, query, category), resource_rows()):
        label, tone = stock_status(item)
        items.append({**{k: item[k] for k in ("id", "name", "category", "stock", "reorder_level")}, "status": label, "tone": tone})
    return jsonify(items=items)


@app.post("/api/inventory")
@api_route("ltsm")
def api_add_inventory(user):
    v = Validator(json_body())
    name = v.text("item_name", "Item name", 1, 100)
    category = v.choice("category", "Category", CATEGORIES)
    stock = v.integer("quantity", "Quantity", 0, 10000)
    reorder = v.integer("reorder_level", "Reorder level", 0, 10000)
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
                  (resource_name, category, quantity_owned, quantity_in_stock,
                   reorder_level, description, unit_of_measure)
                VALUES (%s, %s, %s, %s, %s, %s, 'units')
                """,
                (name, category, stock, stock, reorder, "Added by the LTSM committee"),
            )
            resource_id = cursor.lastrowid
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


def record_inventory_adjustment(cursor, resource_id, movement_id, kind, quantity_change,
                                quantity_before, quantity_after, reason, user_id):
    cursor.execute(
        """
        INSERT INTO inventory_adjustment
          (resource_id, movement_id, adjustment_type, quantity_change,
           quantity_before, quantity_after, reason, recorded_by_user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            resource_id, movement_id, kind, quantity_change,
            quantity_before, quantity_after, reason, user_id,
        ),
    )


@app.get("/api/inventory/adjustments")
@api_route("ltsm")
def api_inventory_adjustments(user):
    items = db.query_all(
        """
        SELECT r.resource_name AS item, a.adjustment_type,
               a.quantity_change, a.quantity_before, a.quantity_after,
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


@app.post("/api/inventory/adjust")
@api_route("ltsm")
def api_adjust_inventory(user):
    v = Validator(json_body())
    item_id = v.integer("item_id", "Item", 1, 10**9)
    action = v.choice("action", "Adjustment", ("add", "remove"))
    quantity = v.integer("quantity", "Quantity", 1, 10000)
    reason = v.text("reason", "Reason", 3, 255)
    v.done()

    quantity_change = quantity if action == "add" else -quantity
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT resource_id, resource_name, quantity_in_stock
                FROM resource
                WHERE resource_id = %s
                FOR UPDATE
                """,
                (item_id,),
            )
            item = cursor.fetchone()
            if not item:
                raise ApiError("Choose an item from the inventory.", 404)

            quantity_after = item["quantity_in_stock"] + quantity_change
            if quantity_after < 0:
                raise ApiError(
                    f"Only {item['quantity_in_stock']} of {item['resource_name']} are in stock.",
                    409,
                    {"quantity": "Cannot remove more than the available stock."},
                )
            cursor.execute(
                "UPDATE resource SET quantity_in_stock = %s WHERE resource_id = %s",
                (quantity_after, item_id),
            )
            record_inventory_adjustment(
                cursor, item_id, None, "manual", quantity_change,
                item["quantity_in_stock"], quantity_after, reason, user["id"],
            )
        connection.commit()
        verb = "added to" if action == "add" else "removed from"
        return jsonify(
            message=f"{quantity} × {item['resource_name']} {verb} stock. "
                    f"Available stock is now {quantity_after}."
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


@app.get("/api/loans")
@api_route("ltsm")
def api_loans(user):
    rows = db.query_all(
        """
        SELECT m.movement_id AS id, m.borrower_name AS borrower,
               r.resource_name AS item, m.quantity, m.due_date AS due
        FROM item_movement AS m
        JOIN resource AS r ON r.resource_id = m.resource_id
        WHERE m.movement_type = 'issue' AND m.active_loan = TRUE
        ORDER BY m.due_date, m.movement_date, m.movement_id
        """
    )
    items = []
    for loan in rows:
        loan["due"] = date_value(loan["due"]) if loan["due"] else None
        label, tone = loan_status(loan)
        items.append({"id": loan["id"], "borrower": loan["borrower"], "item": loan["item"], "quantity": loan["quantity"], "due": loan["due"], "status": label, "tone": tone})
    return jsonify(items=items)


@app.post("/api/movements")
@api_route("ltsm")
def api_movement(user):
    data = json_body()
    v = Validator(data)
    kind = v.choice("movement_type", "Action", ("issue", "return"))
    item_id = v.integer("item_id", "Item", 1, 10**9)
    borrower_id = v.text("borrower_id", "Student / staff number", 1, 40)
    quantity = v.integer("quantity", "Quantity", 1, 100)
    moved_on = v.day("movement_date", "Date", not_after=today())
    due = v.day("due_date", "Due date", not_before=moved_on) if kind == "issue" else None
    v.done()
    connection = db.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT resource_id AS id, resource_name AS name,
                       category, quantity_in_stock AS stock
                FROM resource WHERE resource_id = %s FOR UPDATE
                """,
                (item_id,),
            )
            item = cursor.fetchone()
            if not item:
                raise ApiError("Choose an item from the list.", 400, {"item_id": "Unknown item."})

            if kind == "issue":
                if quantity > item["stock"]:
                    raise ApiError(
                        f"Only {item['stock']} of {item['name']} in stock.",
                        409,
                        {"quantity": "Not enough stock."},
                    )
                cursor.execute(
                    "SELECT full_name FROM users WHERE LOWER(school_id) = LOWER(%s) AND is_active = TRUE LIMIT 1",
                    (borrower_id,),
                )
                borrower_row = cursor.fetchone()
                borrower = borrower_row["full_name"] if borrower_row else borrower_id
                cursor.execute(
                    "UPDATE resource SET quantity_in_stock = quantity_in_stock - %s WHERE resource_id = %s",
                    (quantity, item_id),
                )
                cursor.execute(
                    """
                    INSERT INTO item_movement
                      (resource_id, borrower_id, borrower_name, movement_type,
                       quantity, movement_date, due_date, active_loan, recorded_by_user_id)
                    VALUES (%s, %s, %s, 'issue', %s, %s, %s, TRUE, %s)
                    """,
                    (item_id, borrower_id, borrower, quantity, moved_on, due, user["id"]),
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
                SELECT movement_id, borrower_name, quantity
                FROM item_movement
                WHERE resource_id = %s AND LOWER(borrower_id) = LOWER(%s)
                  AND movement_type = 'issue' AND active_loan = TRUE
                ORDER BY movement_date, movement_id
                FOR UPDATE
                """,
                (item_id, borrower_id),
            )
            borrower_loans = cursor.fetchall()
            loan_total = sum(loan["quantity"] for loan in borrower_loans)
            if not borrower_loans:
                raise ApiError("No active loan found for that borrower and item.", 409)
            if quantity > loan_total:
                raise ApiError(
                    f"That borrower only has {loan_total} on loan.",
                    409,
                    {"quantity": "Too many."},
                )
            remaining_return = quantity
            for loan in borrower_loans:
                returned = min(remaining_return, loan["quantity"])
                remaining = loan["quantity"] - returned
                if returned:
                    cursor.execute(
                        """
                        UPDATE item_movement
                        SET quantity = %s, active_loan = %s
                        WHERE movement_id = %s
                        """,
                        (
                            remaining if remaining else loan["quantity"],
                            remaining > 0,
                            loan["movement_id"],
                        ),
                    )
                    remaining_return -= returned
                if remaining_return == 0:
                    break
            cursor.execute(
                "UPDATE resource SET quantity_in_stock = quantity_in_stock + %s WHERE resource_id = %s",
                (quantity, item_id),
            )
            cursor.execute(
                """
                INSERT INTO item_movement
                  (resource_id, borrower_id, borrower_name, movement_type,
                   quantity, movement_date, active_loan, recorded_by_user_id)
                VALUES (%s, %s, %s, 'return', %s, %s, FALSE, %s)
                """,
                (item_id, borrower_id, borrower_loans[0]["borrower_name"], quantity, moved_on, user["id"]),
            )
            record_inventory_adjustment(
                cursor, item_id, cursor.lastrowid, "return", quantity,
                item["stock"], item["stock"] + quantity,
                f"Returned by {borrower_loans[0]['borrower_name']} ({borrower_id})",
                user["id"],
            )
        connection.commit()
        return jsonify(message=f"Recorded return of {quantity} × {item['name']} from {borrower_loans[0]['borrower_name']}."), 201
    except Exception:
        connection.rollback()
        raise


@app.get("/api/maintenance")
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


@app.post("/api/maintenance")
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


@app.get("/api/committee/requests")
@api_route("ltsm")
def api_committee_requests(user):
    status = request.args.get("status", "").strip()
    sql = """
        SELECT rr.request_id AS id, rr.resource_name AS name,
               u.full_name AS requested_by, rr.submitted_date AS submitted,
               rr.needed_by, rr.quantity, rr.status
        FROM resource_request AS rr
        JOIN users AS u ON u.user_id = rr.user_id
    """
    params = []
    if status:
        sql += " WHERE rr.status = %s"
        params.append(status)
    sql += " ORDER BY rr.submitted_date DESC, rr.request_id DESC"
    rows = db.query_all(sql, params)
    items = []
    for r in rows:
        r["submitted"] = date_value(r["submitted"])
        r["needed_by"] = date_value(r["needed_by"]) if r["needed_by"] else None
        priority, tone = request_priority(r)
        items.append({"id": r["id"], "name": r["name"], "requested_by": r["requested_by"], "submitted": r["submitted"],
                      "quantity": r["quantity"], "status": r["status"], "priority": priority, "priority_tone": tone})
    return jsonify(items=items)


@app.get("/api/committee/suggestions")
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


@app.post("/api/requests/<int:request_id>/decision")
@api_route("ltsm")
def api_decide_request(user, request_id):
    v = Validator(json_body())
    decision = v.choice("decision", "Decision", ("Approved", "Declined"))
    v.done()
    row = db.query_one(
        "SELECT resource_name AS name, status FROM resource_request WHERE request_id = %s",
        (request_id,),
    )
    if row is None:
        raise ApiError("That request does not exist.", 404)
    if row["status"] != "In review":
        raise ApiError(f"{row['name']} was already {row['status'].lower()}.", 409)
    update = "Approved · collection details to follow" if decision == "Approved" else "Declined by the LTSM committee"
    db.execute(
        """
        UPDATE resource_request
        SET status = %s, latest_update = %s
        WHERE request_id = %s AND status = 'In review'
        """,
        (decision, update, request_id),
    )
    return jsonify(message=f"{row['name']} {decision.lower()}.")


@app.get("/api/committee/bookings")
@api_route("ltsm")
def api_committee_bookings(user):
    rows = db.query_all(
        """
        SELECT b.booking_id AS id, r.resource_name AS equipment,
               u.full_name AS booked_by, b.booking_date AS `date`,
               b.start_time AS `start`, b.end_time AS `end`, b.room, b.status
        FROM equipment_booking AS b
        JOIN resource AS r ON r.resource_id = b.resource_id
        JOIN users AS u ON u.user_id = b.user_id
        WHERE b.booking_date >= %s
        ORDER BY b.booking_date, b.start_time, b.booking_id
        """,
        (today(),),
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


@app.post("/api/bookings/<int:booking_id>/decision")
@api_route("ltsm")
def api_decide_booking(user, booking_id):
    v = Validator(json_body())
    decision = v.choice("decision", "Decision", ("Confirmed", "Declined"))
    v.done()
    booking = db.query_one(
        """
        SELECT b.status, r.resource_name AS equipment
        FROM equipment_booking AS b
        JOIN resource AS r ON r.resource_id = b.resource_id
        WHERE b.booking_id = %s
        """,
        (booking_id,),
    )
    if booking is None:
        raise ApiError("That booking does not exist.", 404)
    if booking["status"] != "Awaiting approval":
        raise ApiError(f"That booking was already {booking['status'].lower()}.", 409)
    db.execute(
        """
        UPDATE equipment_booking SET status = %s
        WHERE booking_id = %s AND status = 'Awaiting approval'
        """,
        (decision, booking_id),
    )
    return jsonify(message=f"{booking['equipment']} booking {decision.lower()}.")


@app.get("/api/dashboard/user")
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
        SELECT r.resource_name AS item, m.quantity,
               m.movement_date AS issued, m.due_date AS due
        FROM item_movement AS m
        JOIN resource AS r ON r.resource_id = m.resource_id
        WHERE m.borrower_id = %s
          AND m.movement_type = 'issue'
          AND m.active_loan = TRUE
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


@app.get("/api/dashboard/committee")
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
        "inventory": {"value": sum(i["stock"] for i in resources), "note": f"Across {plural(len({i['category'] for i in resources}), 'category', 'categories')}"},
        "pending_requests": {"value": pending, "note": f"{submitted_today} submitted today"},
        "low_stock": {"value": len(low), "note": "Review replenishment" if low else "Stock levels are healthy"},
        "bookings": {"value": upcoming, "note": f"{due_this_week} due this week"},
    }
    return jsonify(kpis=kpis, low_stock=[{"id": i["id"], "name": i["name"], "stock": i["stock"], "tone": stock_status(i)[1]} for i in low])


def join_phrases(parts):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


@app.get("/api/reports")
@api_route("ltsm")
def api_reports(user):
    resources = resource_rows()
    movement_rows = db.query_all(
        """
        SELECT resource_id, SUM(quantity) AS quantity
        FROM item_movement
        WHERE movement_type = 'issue' AND active_loan = TRUE
        GROUP BY resource_id
        """
    )
    out = Counter({row["resource_id"]: row["quantity"] for row in movement_rows})
    available = sum(i["stock"] for i in resources)
    on_loan = sum(out.values())
    total = available + on_loan
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
        categories.append({"category": name, "total": units + sum(out[i["id"]] for i in group), "available": units, "low_stock": n_low,
                           "condition": "Review stock" if n_low else "Healthy", "tone": "warning" if n_low else "ok"})
    statuses = [{"status": s, "count": counts[s], "tone": REQUEST_TONES[s]} for s in ("Approved", "Ready for collection", "In review", "Declined")]
    return jsonify(summary=summary, categories=categories, requests_by_status=statuses)


@app.get("/health")
def health():
    """Used by hosting platforms and the runbook to check that the app is up."""
    return jsonify(status="ok", time=now().isoformat(timespec="seconds"))


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
