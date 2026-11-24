from flask import Blueprint


pages_bp = Blueprint("pages", __name__)
auth_bp = Blueprint("auth", __name__)
notifications_bp = Blueprint("notifications", __name__)
catalog_bp = Blueprint("catalog", __name__)
requests_bp = Blueprint("requests", __name__)
bookings_bp = Blueprint("bookings", __name__)
inventory_bp = Blueprint("inventory", __name__)
circulation_bp = Blueprint("circulation", __name__)
maintenance_bp = Blueprint("maintenance", __name__)
dashboard_bp = Blueprint("dashboard", __name__)
evidence_bp = Blueprint("evidence", __name__)
reports_bp = Blueprint("reports", __name__)
health_bp = Blueprint("health", __name__)

BLUEPRINTS = (
    pages_bp,
    auth_bp,
    notifications_bp,
    catalog_bp,
    requests_bp,
    bookings_bp,
    inventory_bp,
    circulation_bp,
    maintenance_bp,
    dashboard_bp,
    evidence_bp,
    reports_bp,
    health_bp,
)
