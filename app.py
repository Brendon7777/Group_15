"""
LTSM Portal – Flask application (Task 3A).

Serves the Jinja templates in Templates/ and the JSON API under /api that the
fetch() code in static/js/ calls. See API_CONTRACT.md for every endpoint.

NOTE FOR THE GROUP: the data below lives in Python lists so the front end can be
connected and tested today. When the MySQL layer is ready (see staff.sql), replace
the list operations inside each endpoint with SQL queries - the request/response
shapes in API_CONTRACT.md stay the same, so the JavaScript does not change.

Run:  python app.py   then open http://127.0.0.1:5000
Demo sign-ins (password for all: Password123!):
    teacher  g2.teacher1@example.com      learner  learner01@example.com
    ltsm     ltsm01@example.com
"""
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

try:  # optional: load settings from a local .env file (see .env.example)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

APP_ENV = os.environ.get("APP_ENV", "development")
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Africa/Johannesburg")

app = Flask(__name__, template_folder="Templates", static_folder="static")
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    if APP_ENV == "production":
        raise RuntimeError("SECRET_KEY must be set when APP_ENV=production (see .env.example).")
    _secret = "dev-only-change-me"
app.secret_key = _secret
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=(APP_ENV == "production"))

DEMO_PASSWORD = "Password123!"


def now():
    """Current time in the school's timezone (servers usually run in UTC, which is 2 hours behind South Africa)."""
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def today():
    return now().date()


def days_from_today(n):
    return (today() + timedelta(days=n)).isoformat()


# --------------------------------------------------------------------------- #
# Sample data (replace with database queries)
# --------------------------------------------------------------------------- #
_demo_hash = generate_password_hash(DEMO_PASSWORD)
USERS = [
    {"id": 1, "name": "Ayesha Jacobs", "email": "g2.teacher1@example.com", "school_id": "T-1005", "role": "teacher", "hash": _demo_hash},
    {"id": 2, "name": "Lwazi Mthembu", "email": "learner01@example.com", "school_id": "L-3001", "role": "learner", "hash": _demo_hash},
    {"id": 3, "name": "Nomsa Khumalo", "email": "ltsm01@example.com", "school_id": "C-2001", "role": "ltsm", "hash": _demo_hash},
]

if APP_ENV == "production":
    app.logger.warning("Sample data and demo accounts (published password) are active. Replace them with the database before real use - see docs/RUNBOOK.md.")

ITEMS = [  # one list feeds the catalogue, the inventory page and the booking list
    {"id": 1, "name": "Natural Sciences · Grade 8", "description": "Student textbook · 3rd edition", "category": "Textbooks", "stock": 18, "reorder_level": 10, "unit": "copies"},
    {"id": 2, "name": "Mathematics · Grade 7", "description": "Core learning textbook · 2nd edition", "category": "Textbooks", "stock": 4, "reorder_level": 8, "unit": "copies"},
    {"id": 3, "name": "A4 Exercise Books", "description": "72-page ruled books · packs of 10", "category": "Stationery", "stock": 8, "reorder_level": 15, "unit": "packs"},
    {"id": 4, "name": "Whiteboard Markers", "description": "Assorted colours · classroom pack", "category": "Stationery", "stock": 12, "reorder_level": 10, "unit": "packs"},
    {"id": 5, "name": "Classroom Projector", "description": "HD projector with HDMI connection", "category": "Equipment", "stock": 2, "reorder_level": 1, "unit": "units"},
    {"id": 6, "name": "Tablet Set · 10 devices", "description": "Shared tablet set for classroom activities", "category": "Equipment", "stock": 1, "reorder_level": 1, "unit": "sets"},
    {"id": 7, "name": "Portable Speaker", "description": "Bluetooth speaker for classroom audio", "category": "Equipment", "stock": 3, "reorder_level": 1, "unit": "units"},
    {"id": 8, "name": "Document Camera", "description": "USB camera for live demonstrations", "category": "Equipment", "stock": 1, "reorder_level": 1, "unit": "units"},
    {"id": 9, "name": "Geometry Set", "description": "Compass, protractor and rulers", "category": "Stationery", "stock": 20, "reorder_level": 10, "unit": "sets"},
]
CATEGORIES = ["Textbooks", "Stationery", "Equipment", "Other"]
CATEGORY_WORD = {"Textbooks": "textbook", "Stationery": "stationery", "Equipment": "equipment", "Other": "other"}

REQUESTS = [
    {"id": 1, "user_id": 1, "name": "Grade 8 science workbook", "category": "Textbooks", "submitted": days_from_today(-10), "quantity": 30, "status": "In review", "update": "Committee review in progress", "needed_by": days_from_today(4)},
    {"id": 2, "user_id": 1, "name": "Whiteboard markers", "category": "Stationery", "submitted": days_from_today(-14), "quantity": 2, "status": "Approved", "update": "Approved · collection details to follow"},
    {"id": 3, "user_id": 1, "name": "Geometry sets", "category": "Stationery", "submitted": days_from_today(-19), "quantity": 5, "status": "Ready for collection", "update": "Collect from the resource office"},
    {"id": 4, "user_id": 1, "name": "Personal laptop", "category": "Equipment", "submitted": days_from_today(-24), "quantity": 1, "status": "Declined", "update": "Outside the school equipment catalogue"},
    {"id": 5, "user_id": 2, "name": "Whiteboard markers (class pack)", "category": "Stationery", "submitted": days_from_today(-2), "quantity": 3, "status": "In review", "update": "Committee review in progress", "needed_by": days_from_today(9)},
    {"id": 6, "user_id": 2, "name": "Calculator set", "category": "Equipment", "submitted": days_from_today(-3), "quantity": 1, "status": "In review", "update": "Committee review in progress", "needed_by": days_from_today(2)},
]
REQUEST_TONES = {"In review": "warning", "Approved": "ok", "Ready for collection": "blue", "Declined": "danger"}

BOOKINGS = [
    {"id": 1, "user_id": 1, "item_id": 5, "date": days_from_today(3), "start": "10:00", "end": "12:00", "room": "Room 12", "purpose": "Mathematics lesson", "status": "Confirmed"},
    {"id": 2, "user_id": 2, "item_id": 6, "date": days_from_today(4), "start": "09:00", "end": "10:00", "room": "Library", "purpose": "Research task", "status": "Awaiting approval"},
]
BOOKING_TONES = {"Confirmed": "ok", "Awaiting approval": "warning", "Declined": "danger"}
LOANS = [
    {"id": 1, "borrower_id": "L-2041", "borrower": "A. Mokoena", "item_id": 1, "quantity": 1, "issued": days_from_today(-10), "due": days_from_today(5), "active": True},
    {"id": 2, "borrower_id": "T-1005", "borrower": "Ayesha Jacobs", "item_id": 5, "quantity": 1, "issued": days_from_today(-6), "due": days_from_today(2), "active": True},
    {"id": 3, "borrower_id": "L-2087", "borrower": "T. Dlamini", "item_id": 9, "quantity": 1, "issued": days_from_today(-17), "due": days_from_today(-3), "active": True},
    {"id": 4, "borrower_id": "T-1005", "borrower": "Ayesha Jacobs", "item_id": 1, "quantity": 1, "issued": days_from_today(-2), "due": days_from_today(12), "active": True},
]
MAINTENANCE = [
    {"id": 1, "item": "Projector · PRJ-014", "issue": "HDMI connection intermittent", "reported": days_from_today(-10), "status": "In repair", "priority": "High", "reported_by": "Nomsa Khumalo"},
    {"id": 2, "item": "Tablet · TAB-022", "issue": "Screen does not respond", "reported": days_from_today(-12), "status": "Out of service", "priority": "Urgent", "reported_by": "Nomsa Khumalo"},
    {"id": 3, "item": "Speaker · SPK-005", "issue": "Battery replacement", "reported": days_from_today(-15), "status": "Resolved", "priority": "Low", "reported_by": "Nomsa Khumalo"},
]
MAINTENANCE_TONES = {"Open": "warning", "In repair": "warning", "Out of service": "danger", "Resolved": "ok"}


def next_id(rows):
    return max((row["id"] for row in rows), default=0) + 1


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
    return next((u for u in USERS if u["id"] == session.get("uid")), None)


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


def item_by_id(item_id):
    return next((i for i in ITEMS if i["id"] == item_id), None)


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
PUBLIC_PAGES = {"index", "login", "register"}
USER_PAGES = {"user-dashboard", "view-resources", "request-resources", "my-requests", "book-equipment"}
COMMITTEE_PAGES = {"ltsm-dashboard", "manage-inventory", "issue-return", "maintenance", "reports"}


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
    if page in PUBLIC_PAGES:
        return render_template(f"{page}.html")
    user = current_user()
    if user is None:
        return redirect("/login")
    if page in COMMITTEE_PAGES and user["role"] != "ltsm":
        return redirect(dashboard_for(user))
    return render_template(f"{page}.html")


# --------------------------------------------------------------------------- #
# API: accounts
# --------------------------------------------------------------------------- #
@app.post("/api/login")
def api_login():
    data = json_body()
    username = str(data.get("username", "")).strip().lower()
    user = next((u for u in USERS if username in (u["email"].lower(), u["school_id"].lower())), None)
    if not (user and user["role"] == data.get("role") and check_password_hash(user["hash"], str(data.get("password", "")))):
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
    if any(u["email"].lower() == email for u in USERS):
        raise ApiError("An account with that email address already exists.", 409, {"email": "Already registered."})
    if any(u["school_id"].lower() == school_id.lower() for u in USERS):
        raise ApiError("An account with that student / staff number already exists.", 409, {"school_id": "Already registered."})
    USERS.append({"id": next_id(USERS), "name": name, "email": email, "school_id": school_id, "role": role, "hash": generate_password_hash(password)})
    return jsonify(message="Account created."), 201


# --------------------------------------------------------------------------- #
# API: teacher / learner features
# --------------------------------------------------------------------------- #
@app.get("/api/resources")
@api_route()
def api_resources(user):
    query, category = request.args.get("q", "").strip(), request.args.get("category", "").strip()
    items = []
    for item in filter(lambda i: matches(i, query, category), ITEMS):
        label, tone = availability(item)
        items.append({**{k: item[k] for k in ("id", "name", "description", "category", "stock", "unit")}, "availability": label, "tone": tone})
    return jsonify(items=items)


@app.post("/api/requests")
@api_route()
def api_create_request(user):
    v = Validator(json_body())
    row = {
        "id": next_id(REQUESTS), "user_id": user["id"],
        "name": v.text("resource_name", "Resource name", 1, 100),
        "category": v.choice("category", "Category", CATEGORIES),
        "quantity": v.integer("quantity", "Quantity", 1, 100),
        "needed_by": v.day("needed_by", "Needed by", not_before=today()),
        "purpose": v.text("purpose", "Reason for request", 10, 500),
    }
    v.done()
    row["needed_by"] = row["needed_by"].isoformat()
    row.update(submitted=today().isoformat(), status="In review", update="Committee review in progress")
    REQUESTS.append(row)
    return jsonify(message="Request submitted.", id=row["id"]), 201


@app.get("/api/requests")
@api_route()
def api_my_requests(user):
    status = request.args.get("status", "").strip()
    rows = [r for r in REQUESTS if r["user_id"] == user["id"] and (not status or r["status"] == status)]
    rows.sort(key=lambda r: (r["submitted"], r["id"]), reverse=True)
    keys = ("id", "name", "category", "submitted", "quantity", "status", "update")
    return jsonify(items=[{**{k: r[k] for k in keys}, "needed_by": r.get("needed_by"), "tone": REQUEST_TONES[r["status"]]} for r in rows])


@app.get("/api/equipment")
@api_route()
def api_equipment(user):
    return jsonify(items=[{"id": i["id"], "name": i["name"], "stock": i["stock"]} for i in ITEMS if i["category"] == "Equipment"])


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
    item = item_by_id(equipment_id)
    if not item or item["category"] != "Equipment":
        raise ApiError("Choose equipment from the list.", 400, {"equipment_id": "Unknown equipment."})
    overlapping = [b for b in BOOKINGS if b["status"] != "Declined" and b["item_id"] == item["id"] and b["date"] == day.isoformat() and start < b["end"] and b["start"] < end]
    if len(overlapping) >= item["stock"]:
        raise ApiError(f"No {item['name']} is free on {day.isoformat()} between {start} and {end}. Try another time.", 409)
    BOOKINGS.append({"id": next_id(BOOKINGS), "user_id": user["id"], "item_id": item["id"], "date": day.isoformat(), "start": start, "end": end, "room": room, "purpose": purpose, "status": "Awaiting approval"})
    return jsonify(message=f"Booking requested: {item['name']} on {day.isoformat()}, {start}–{end}. The LTSM committee will confirm it."), 201


@app.get("/api/bookings")
@api_route()
def api_my_bookings(user):
    rows = upcoming_bookings(user_id=user["id"], include_declined=True)
    return jsonify(items=[{"id": b["id"], "equipment": item_by_id(b["item_id"])["name"], "date": b["date"], "start": b["start"], "end": b["end"], "room": b["room"], "purpose": b["purpose"], "status": b["status"], "tone": BOOKING_TONES[b["status"]]} for b in rows])


# --------------------------------------------------------------------------- #
# API: LTSM committee features
# --------------------------------------------------------------------------- #
@app.get("/api/inventory")
@api_route("ltsm")
def api_inventory(user):
    query, category = request.args.get("q", "").strip(), request.args.get("category", "").strip()
    items = []
    for item in filter(lambda i: matches(i, query, category), ITEMS):
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
    if any(i["name"].lower() == name.lower() for i in ITEMS):
        raise ApiError(f"{name} is already in the inventory.", 409, {"item_name": "Already exists."})
    ITEMS.append({"id": next_id(ITEMS), "name": name, "description": "Added by the LTSM committee", "category": category, "stock": stock, "reorder_level": reorder, "unit": "units"})
    return jsonify(message=f"{name} added to the inventory."), 201


def loan_status(loan):
    remaining = (date.fromisoformat(loan["due"]) - today()).days
    if remaining < 0:
        return "Overdue", "danger"
    return ("Due soon", "warning") if remaining <= 3 else ("On loan", "ok")


@app.get("/api/loans")
@api_route("ltsm")
def api_loans(user):
    rows = sorted((l for l in LOANS if l["active"]), key=lambda l: l["due"])
    items = []
    for loan in rows:
        label, tone = loan_status(loan)
        items.append({"id": loan["id"], "borrower": loan["borrower"], "item": item_by_id(loan["item_id"])["name"], "quantity": loan["quantity"], "due": loan["due"], "status": label, "tone": tone})
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
    item = item_by_id(item_id)
    if not item:
        raise ApiError("Choose an item from the list.", 400, {"item_id": "Unknown item."})

    if kind == "issue":
        if quantity > item["stock"]:
            raise ApiError(f"Only {item['stock']} of {item['name']} in stock.", 409, {"quantity": "Not enough stock."})
        borrower = next((u["name"] for u in USERS if u["school_id"].lower() == borrower_id.lower()), borrower_id)
        item["stock"] -= quantity
        LOANS.append({"id": next_id(LOANS), "borrower_id": borrower_id, "borrower": borrower, "item_id": item["id"], "quantity": quantity, "issued": moved_on.isoformat(), "due": due.isoformat(), "active": True})
        return jsonify(message=f"Issued {quantity} × {item['name']} to {borrower}, due {due.isoformat()}."), 201

    loan = next((l for l in LOANS if l["active"] and l["item_id"] == item["id"] and l["borrower_id"].lower() == borrower_id.lower()), None)
    if loan is None:
        raise ApiError("No active loan found for that borrower and item.", 409)
    if quantity > loan["quantity"]:
        raise ApiError(f"That borrower only has {loan['quantity']} on loan.", 409, {"quantity": "Too many."})
    loan["quantity"] -= quantity
    loan["active"] = loan["quantity"] > 0
    item["stock"] += quantity
    return jsonify(message=f"Recorded return of {quantity} × {item['name']} from {loan['borrower']}."), 201


@app.get("/api/maintenance")
@api_route("ltsm")
def api_maintenance(user):
    rows = sorted(MAINTENANCE, key=lambda m: (m["reported"], m["id"]), reverse=True)
    this_month = today().strftime("%Y-%m")
    summary = {
        "open": sum(m["status"] == "Open" for m in rows),
        "in_repair": sum(m["status"] == "In repair" for m in rows),
        "resolved": sum(m["status"] == "Resolved" and m["reported"].startswith(this_month) for m in rows),
        "out_of_service": sum(m["status"] == "Out of service" for m in rows),
    }
    items = [{**{k: m[k] for k in ("id", "item", "issue", "reported", "status", "priority")}, "tone": MAINTENANCE_TONES[m["status"]]} for m in rows]
    return jsonify(items=items, summary=summary)


@app.post("/api/maintenance")
@api_route("ltsm")
def api_log_maintenance(user):
    v = Validator(json_body())
    row = {
        "id": next_id(MAINTENANCE),
        "item": v.text("equipment", "Equipment / item", 1, 100),
        "reported_by": v.text("reported_by", "Reported by", 1, 80),
        "priority": v.choice("priority", "Priority", ("Low", "Normal", "High", "Urgent")),
        "reported": (v.day("date", "Date reported", not_after=today()) or today()).isoformat(),
        "issue": v.text("description", "Description", 10, 500),
        "status": "Open",
    }
    v.done()
    MAINTENANCE.append(row)
    return jsonify(message=f"Issue logged for {row['item']}."), 201


# --------------------------------------------------------------------------- #
# Task 3B: approval workflows, dashboard KPIs and reports
# --------------------------------------------------------------------------- #
def upcoming_bookings(user_id=None, include_declined=False):
    """Bookings from today onwards, soonest first (optionally only one user's)."""
    rows = [b for b in BOOKINGS
            if b["date"] >= today().isoformat()
            and (user_id is None or b["user_id"] == user_id)
            and (include_declined or b["status"] != "Declined")]
    return sorted(rows, key=lambda b: (b["date"], b["start"], b["id"]))


def user_name(user_id):
    return next((u["name"] for u in USERS if u["id"] == user_id), "Unknown user")


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


def on_loan_units():
    """{item_id: units currently out on loan}"""
    totals = Counter()
    for loan in LOANS:
        if loan["active"]:
            totals[loan["item_id"]] += loan["quantity"]
    return totals


@app.get("/api/committee/requests")
@api_route("ltsm")
def api_committee_requests(user):
    status = request.args.get("status", "").strip()
    rows = sorted((r for r in REQUESTS if not status or r["status"] == status), key=lambda r: (r["submitted"], r["id"]), reverse=True)
    items = []
    for r in rows:
        priority, tone = request_priority(r)
        items.append({"id": r["id"], "name": r["name"], "requested_by": user_name(r["user_id"]), "submitted": r["submitted"],
                      "quantity": r["quantity"], "status": r["status"], "priority": priority, "priority_tone": tone})
    return jsonify(items=items)


@app.post("/api/requests/<int:request_id>/decision")
@api_route("ltsm")
def api_decide_request(user, request_id):
    v = Validator(json_body())
    decision = v.choice("decision", "Decision", ("Approved", "Declined"))
    v.done()
    row = next((r for r in REQUESTS if r["id"] == request_id), None)
    if row is None:
        raise ApiError("That request does not exist.", 404)
    if row["status"] != "In review":
        raise ApiError(f"{row['name']} was already {row['status'].lower()}.", 409)
    row["status"] = decision
    row["update"] = "Approved · collection details to follow" if decision == "Approved" else "Declined by the LTSM committee"
    return jsonify(message=f"{row['name']} {decision.lower()}.")


@app.get("/api/committee/bookings")
@api_route("ltsm")
def api_committee_bookings(user):
    return jsonify(items=[{"id": b["id"], "equipment": item_by_id(b["item_id"])["name"], "booked_by": user_name(b["user_id"]), "date": b["date"],
                           "start": b["start"], "end": b["end"], "room": b["room"], "status": b["status"], "tone": BOOKING_TONES[b["status"]]}
                          for b in upcoming_bookings(include_declined=True)])


@app.post("/api/bookings/<int:booking_id>/decision")
@api_route("ltsm")
def api_decide_booking(user, booking_id):
    v = Validator(json_body())
    decision = v.choice("decision", "Decision", ("Confirmed", "Declined"))
    v.done()
    booking = next((b for b in BOOKINGS if b["id"] == booking_id), None)
    if booking is None:
        raise ApiError("That booking does not exist.", 404)
    if booking["status"] != "Awaiting approval":
        raise ApiError(f"That booking was already {booking['status'].lower()}.", 409)
    booking["status"] = decision
    return jsonify(message=f"{item_by_id(booking['item_id'])['name']} booking {decision.lower()}.")


@app.get("/api/dashboard/user")
@api_route()
def api_user_dashboard(user):
    in_stock = [i for i in ITEMS if i["stock"] > 0]
    mine = [r for r in REQUESTS if r["user_id"] == user["id"]]
    open_requests = [r for r in mine if r["status"] in ("In review", "Approved", "Ready for collection")]
    waiting = sum(r["status"] == "In review" for r in mine)
    bookings = upcoming_bookings(user_id=user["id"])
    loans = sorted((l for l in LOANS if l["active"] and l["borrower_id"].lower() == user["school_id"].lower()), key=lambda l: l["due"])
    due_soon = sum(loan_status(l)[0] != "On loan" for l in loans)
    next_booking = None
    if bookings:
        b = bookings[0]
        next_booking = {"equipment": item_by_id(b["item_id"])["name"], "date": b["date"], "start": b["start"], "end": b["end"], "room": b["room"],
                        "purpose": b["purpose"], "status": b["status"], "tone": BOOKING_TONES[b["status"]]}
    categories = []
    for name in ("Textbooks", "Stationery", "Equipment"):
        group = [i for i in ITEMS if i["category"] == name]
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
        loan_rows.append({"item": item_by_id(l["item_id"])["name"], "quantity": l["quantity"], "issued": l["issued"], "due": l["due"], "status": label, "tone": tone})
    kpis = {
        "available_resources": {"value": sum(i["stock"] for i in in_stock), "note": f"Across {plural(len({i['category'] for i in in_stock}), 'category', 'categories')}"},
        "open_requests": {"value": len(open_requests), "note": f"{waiting} awaiting review"},
        "bookings": {"value": len(bookings), "note": f"Next: {date.fromisoformat(bookings[0]['date']).day} {date.fromisoformat(bookings[0]['date']).strftime('%B')}" if bookings else "No upcoming bookings"},
        "issued": {"value": sum(l["quantity"] for l in loans), "note": f"{plural(due_soon, 'return')} due soon" if due_soon else "Nothing due soon"},
    }
    return jsonify(kpis=kpis, categories=categories, loans=loan_rows, next_booking=next_booking)


@app.get("/api/dashboard/committee")
@api_route("ltsm")
def api_committee_dashboard(user):
    low = sorted((i for i in ITEMS if stock_status(i)[0] != "In stock"), key=lambda i: i["stock"] / max(i["reorder_level"], 1))
    pending = [r for r in REQUESTS if r["status"] == "In review"]
    upcoming = upcoming_bookings()
    week_end = (today() + timedelta(days=7)).isoformat()
    kpis = {
        "inventory": {"value": sum(i["stock"] for i in ITEMS), "note": f"Across {plural(len({i['category'] for i in ITEMS}), 'category', 'categories')}"},
        "pending_requests": {"value": len(pending), "note": f"{sum(r['submitted'] == today().isoformat() for r in pending)} submitted today"},
        "low_stock": {"value": len(low), "note": "Review replenishment" if low else "Stock levels are healthy"},
        "bookings": {"value": len(upcoming), "note": f"{sum(b['date'] <= week_end for b in upcoming)} due this week"},
    }
    return jsonify(kpis=kpis, low_stock=[{"id": i["id"], "name": i["name"], "stock": i["stock"], "tone": stock_status(i)[1]} for i in low])


def join_phrases(parts):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


@app.get("/api/reports")
@api_route("ltsm")
def api_reports(user):
    out = on_loan_units()
    available = sum(i["stock"] for i in ITEMS)
    on_loan = sum(out.values())
    total = available + on_loan
    low = [i for i in ITEMS if stock_status(i)[0] != "In stock"]
    low_by_category = Counter(i["category"] for i in low)
    counts = Counter(r["status"] for r in REQUESTS)
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
        group = [i for i in ITEMS if i["category"] == name]
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
