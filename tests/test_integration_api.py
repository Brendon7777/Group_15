"""Integration tests: the Flask routes, sessions, role permissions and the end-to-end workflows, through the real HTTP layer."""
import re
import unittest
from pathlib import Path

from base import AppTestCase, CREDENTIALS, PASSWORD

COMMITTEE_ONLY = [
    ("get", "/api/inventory"), ("get", "/api/loans"), ("get", "/api/maintenance"), ("get", "/api/committee/requests"),
    ("get", "/api/committee/bookings"), ("get", "/api/dashboard/committee"), ("get", "/api/reports"),
    ("post", "/api/inventory"), ("post", "/api/movements"), ("post", "/api/maintenance"),
    ("post", "/api/requests/1/decision"), ("post", "/api/bookings/1/decision"),
]
SIGNED_IN_ONLY = [("get", "/api/resources"), ("get", "/api/requests"), ("get", "/api/equipment"), ("get", "/api/bookings"),
                  ("get", "/api/dashboard/user"), ("post", "/api/requests"), ("post", "/api/bookings")]


class AuthTests(AppTestCase):
    def login(self, role="teacher", username=None, password=PASSWORD):
        return self.client.post("/api/login", json={"role": role, "username": username or CREDENTIALS[role], "password": password})

    def test_each_role_is_sent_to_its_own_dashboard(self):
        self.assertEqual(self.json(self.login("teacher"))["redirect"], "/user-dashboard.html")
        self.assertEqual(self.json(self.login("learner"))["redirect"], "/user-dashboard.html")
        self.assertEqual(self.json(self.login("ltsm"))["redirect"], "/ltsm-dashboard.html")

    def test_username_can_be_the_email_in_any_case_or_the_staff_number(self):
        self.assertEqual(self.login(username="G2.Teacher1@Example.com").status_code, 200)
        self.assertEqual(self.login(username="t-1005").status_code, 200)

    def test_failed_logins_all_look_the_same(self):
        """The same message for wrong password, wrong role and unknown user, so accounts cannot be probed."""
        messages = {self.json(r, 401)["error"] for r in (self.login(password="wrong"), self.login(role="ltsm", username=CREDENTIALS["teacher"]),
                                                          self.login(username="nobody@example.com"))}
        self.assertEqual(len(messages), 1)

    def test_login_needs_json(self):
        self.assertEqual(self.client.post("/api/login", data="role=teacher&username=x&password=y").status_code, 415)
        self.assertEqual(self.client.post("/api/login", json=["not", "an", "object"]).status_code, 400)

    def test_logout_ends_the_session(self):
        self.login()
        self.assertEqual(self.client.get("/api/resources").status_code, 200)
        self.json(self.client.post("/api/logout", json={}))
        self.assertEqual(self.client.get("/api/resources").status_code, 401)

    def test_session_cookie_is_httponly_and_samesite(self):
        cookie = self.login().headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_registration_then_sign_in(self):
        body = {"full_name": "New Teacher", "account_type": "teacher", "school_id": "T-9999", "email": "new@example.com", "password": "longenough", "confirm_password": "longenough"}
        self.assertEqual(self.client.post("/api/register", json={**body, "confirm_password": "different"}).status_code, 400)
        self.assertEqual(self.client.post("/api/register", json={**body, "password": "short", "confirm_password": "short"}).status_code, 400)
        self.assertEqual(self.client.post("/api/register", json={**body, "account_type": "ltsm"}).status_code, 400)   # nobody can self-register as committee
        self.assertEqual(self.client.post("/api/register", json=body).status_code, 201)
        self.assertEqual(self.client.post("/api/register", json=body).status_code, 409)                              # duplicate email
        self.assertEqual(self.client.post("/api/register", json={**body, "email": "other@example.com"}).status_code, 409)   # duplicate number
        self.assertEqual(self.login(role="teacher", username="NEW@example.com", password="longenough").status_code, 200)

    def test_passwords_are_stored_hashed(self):
        self.assertTrue(all(u["hash"] != PASSWORD and ":" in u["hash"] for u in self.app_module.USERS))


class PermissionTests(AppTestCase):
    def call(self, client, method, path):
        return getattr(client, method)(path, json={}) if method == "post" else client.get(path)

    def test_anonymous_visitors_get_401_everywhere(self):
        for method, path in COMMITTEE_ONLY + SIGNED_IN_ONLY:
            with self.subTest(path=path, method=method):
                self.assertEqual(self.call(self.client, method, path).status_code, 401)

    def test_teachers_and_learners_cannot_use_committee_endpoints(self):
        for role in ("teacher", "learner"):
            client = self.sign_in(role)
            for method, path in COMMITTEE_ONLY:
                with self.subTest(role=role, path=path, method=method):
                    self.assertEqual(self.call(client, method, path).status_code, 403)

    def test_requests_and_bookings_are_private_to_their_owner(self):
        teacher, learner = self.sign_in("teacher"), self.sign_in("learner")
        self.assertEqual(len(self.json(teacher.get("/api/requests"))["items"]), 4)
        self.assertEqual(self.json(learner.get("/api/requests"))["items"][0]["name"] in {"Whiteboard markers (class pack)", "Calculator set"}, True)
        self.assertEqual({b["equipment"] for b in self.json(teacher.get("/api/bookings"))["items"]}, {"Classroom Projector"})

    def test_pages_redirect_by_role(self):
        self.assertEqual(self.client.get("/my-requests.html").headers["Location"], "/login")
        self.assertEqual(self.client.get("/ltsm-dashboard.html").headers["Location"], "/login")
        teacher, committee = self.sign_in("teacher"), self.sign_in("ltsm")
        self.assertEqual(teacher.get("/manage-inventory.html").headers["Location"], "/user-dashboard.html")
        self.assertEqual(teacher.get("/my-requests.html").status_code, 200)
        self.assertEqual(committee.get("/maintenance.html").status_code, 200)
        self.assertEqual(committee.get("/view-resources.html").status_code, 200)

    def test_public_pages_and_unknown_pages(self):
        for path in ("/", "/index.html", "/login", "/login.html", "/register", "/register.html"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/base.html").status_code, 404)        # the layout template is not a page
        self.assertEqual(self.client.get("/nope.html").status_code, 404)

    def test_health_check_needs_no_sign_in(self):
        body = self.json(self.client.get("/health"))
        self.assertEqual(body["status"], "ok")

    def test_api_errors_are_json_and_never_cached(self):
        missing = self.client.get("/api/does-not-exist")
        self.assertEqual(missing.status_code, 404)
        self.assertIn("error", missing.get_json())
        self.assertEqual(self.client.get("/api/resources").headers["Cache-Control"], "no-store")
        self.assertEqual(self.client.delete("/api/resources").status_code, 405)


class ValidationTests(AppTestCase):
    def test_request_form_collects_every_error(self):
        response = self.sign_in("teacher").post("/api/requests", json={"resource_name": "", "category": "x", "quantity": 0, "needed_by": "2020-01-01", "purpose": "short"})
        body = self.json(response, 400)
        self.assertEqual(set(body["fields"]), {"resource_name", "category", "quantity", "needed_by", "purpose"})

    def test_booleans_and_floats_are_not_accepted_as_quantities(self):
        teacher = self.sign_in("teacher")
        base = {"resource_name": "Chalk", "category": "Other", "needed_by": self.day(2), "purpose": "for the classroom board"}
        self.assertEqual(teacher.post("/api/requests", json={**base, "quantity": True}).status_code, 400)
        self.assertEqual(teacher.post("/api/requests", json={**base, "quantity": 2.5}).status_code, 400)
        self.assertEqual(teacher.post("/api/requests", json={**base, "quantity": "3"}).status_code, 201)

    def test_dates_are_checked_against_the_school_calendar(self):
        committee = self.sign_in("ltsm")
        issue = {"movement_type": "issue", "item_id": 9, "borrower_id": "L-3001", "quantity": 1, "movement_date": self.day(0), "due_date": self.day(7)}
        self.assertEqual(committee.post("/api/movements", json=issue).status_code, 201)
        self.assertEqual(committee.post("/api/movements", json={**issue, "movement_date": self.day(1)}).status_code, 400)   # cannot record the future
        self.assertEqual(committee.post("/api/movements", json={**issue, "due_date": self.day(-1)}).status_code, 400)       # due before issue
        self.assertEqual(committee.post("/api/maintenance", json={"equipment": "x", "reported_by": "y", "priority": "Low", "date": self.day(1), "description": "ten chars+"}).status_code, 400)

    def test_decisions_reject_unknown_values_and_ids(self):
        committee = self.sign_in("ltsm")
        self.assertEqual(committee.post("/api/requests/1/decision", json={"decision": "Maybe"}).status_code, 400)
        self.assertEqual(committee.post("/api/requests/999/decision", json={"decision": "Approved"}).status_code, 404)
        self.assertEqual(committee.post("/api/bookings/999/decision", json={"decision": "Confirmed"}).status_code, 404)
        self.assertEqual(committee.post("/api/bookings/2/decision", json={"decision": "Approved"}).status_code, 400)   # wrong word for bookings


class RequestWorkflowTests(AppTestCase):
    """Workflow 1: teacher submits a request -> committee decides on the dashboard -> teacher sees the outcome."""

    def submit(self, teacher, needed_in=1, name="Chalk boxes"):
        body = {"resource_name": name, "category": "Other", "quantity": 6, "needed_by": self.day(needed_in), "purpose": "Needed for the new Grade 5 board"}
        return self.json(teacher.post("/api/requests", json=body), 201)["id"]

    def pending_kpi(self, committee):
        return self.json(committee.get("/api/dashboard/committee"))["kpis"]["pending_requests"]["value"]

    def test_approved_request(self):
        teacher, committee = self.sign_in("teacher"), self.sign_in("ltsm")
        before = self.pending_kpi(committee)
        request_id = self.submit(teacher)
        queue = self.json(committee.get("/api/committee/requests?status=In review"))["items"]
        self.assertEqual(queue[0]["id"], request_id)
        self.assertEqual((queue[0]["requested_by"], queue[0]["priority"]), ("Ayesha Jacobs", "High"))   # needed tomorrow
        self.assertEqual(self.pending_kpi(committee), before + 1)

        self.assertIn("approved", self.json(committee.post(f"/api/requests/{request_id}/decision", json={"decision": "Approved"}))["message"])
        mine = self.json(teacher.get("/api/requests"))["items"][0]
        self.assertEqual((mine["name"], mine["status"], mine["tone"]), ("Chalk boxes", "Approved", "ok"))
        self.assertEqual(self.pending_kpi(committee), before)
        self.assertEqual(committee.post(f"/api/requests/{request_id}/decision", json={"decision": "Declined"}).status_code, 409)   # cannot decide twice

    def test_declined_request_stops_counting_as_open_for_the_teacher(self):
        teacher, committee = self.sign_in("teacher"), self.sign_in("ltsm")
        open_before = self.json(teacher.get("/api/dashboard/user"))["kpis"]["open_requests"]
        request_id = self.submit(teacher, needed_in=10)
        self.assertEqual(self.json(teacher.get("/api/dashboard/user"))["kpis"]["open_requests"]["value"], open_before["value"] + 1)
        committee.post(f"/api/requests/{request_id}/decision", json={"decision": "Declined"})
        self.assertEqual(self.json(teacher.get("/api/dashboard/user"))["kpis"]["open_requests"]["value"], open_before["value"])
        self.assertEqual(self.json(teacher.get("/api/requests?status=Declined"))["items"][0]["update"], "Declined by the LTSM committee")

    def test_priority_follows_the_needed_by_date(self):
        teacher, committee = self.sign_in("teacher"), self.sign_in("ltsm")
        ids = {days: self.submit(teacher, days, f"Item {days}") for days in (1, 6, 20)}
        priorities = {r["id"]: r["priority"] for r in self.json(committee.get("/api/committee/requests"))["items"]}
        self.assertEqual([priorities[ids[1]], priorities[ids[6]], priorities[ids[20]]], ["High", "Medium", "Normal"])


class BookingWorkflowTests(AppTestCase):
    """Workflow 2: book equipment -> committee confirms or declines -> a declined slot becomes free again."""

    def book(self, client, start="09:00", end="10:00", offset=2):
        tablet = next(i["id"] for i in self.json(client.get("/api/equipment"))["items"] if i["name"].startswith("Tablet"))
        return client.post("/api/bookings", json={"equipment_id": tablet, "booking_date": self.day(offset), "start_time": start, "end_time": end, "room": "Library", "purpose": "Reading project"})

    def test_booking_waits_for_approval_then_is_confirmed(self):
        teacher, committee = self.sign_in("teacher"), self.sign_in("ltsm")
        response = self.book(teacher)
        self.assertIn("committee will confirm", self.json(response, 201)["message"])
        mine = [b for b in self.json(teacher.get("/api/bookings"))["items"] if b["equipment"].startswith("Tablet")][0]
        self.assertEqual(mine["status"], "Awaiting approval")
        waiting = [b for b in self.json(committee.get("/api/committee/bookings"))["items"] if b["booked_by"] == "Ayesha Jacobs" and b["equipment"].startswith("Tablet")][0]
        self.json(committee.post(f"/api/bookings/{waiting['id']}/decision", json={"decision": "Confirmed"}))
        self.assertEqual([b["status"] for b in self.json(teacher.get("/api/bookings"))["items"] if b["equipment"].startswith("Tablet")], ["Confirmed"])
        self.assertEqual(committee.post(f"/api/bookings/{waiting['id']}/decision", json={"decision": "Declined"}).status_code, 409)

    def test_overlapping_bookings_are_refused_but_back_to_back_is_fine(self):
        teacher, learner = self.sign_in("teacher"), self.sign_in("learner")
        self.assertEqual(self.book(teacher, "09:00", "10:00").status_code, 201)
        clash = self.json(self.book(learner, "09:30", "10:30"), 409)
        self.assertIn("No Tablet Set", clash["error"])
        self.assertEqual(self.book(learner, "10:00", "11:00").status_code, 201)
        self.assertEqual(self.book(learner, "10:00", "09:00").status_code, 400)

    def test_declining_frees_the_slot_for_someone_else(self):
        teacher, learner, committee = self.sign_in("teacher"), self.sign_in("learner"), self.sign_in("ltsm")
        self.book(teacher)
        booking = [b for b in self.json(committee.get("/api/committee/bookings"))["items"] if b["booked_by"] == "Ayesha Jacobs" and b["equipment"].startswith("Tablet")][0]
        self.assertEqual(self.book(learner).status_code, 409)
        committee.post(f"/api/bookings/{booking['id']}/decision", json={"decision": "Declined"})
        self.assertEqual(self.book(learner).status_code, 201)
        self.assertEqual([b["status"] for b in self.json(teacher.get("/api/bookings"))["items"] if b["equipment"].startswith("Tablet")], ["Declined"])

    def test_dashboard_shows_the_next_booking_and_count(self):
        teacher = self.sign_in("teacher")
        before = self.json(teacher.get("/api/dashboard/user"))
        self.assertEqual((before["kpis"]["bookings"]["value"], before["next_booking"]["equipment"]), (1, "Classroom Projector"))
        self.book(teacher)                                   # two days away: earlier than the seeded projector booking
        after = self.json(teacher.get("/api/dashboard/user"))
        self.assertEqual(after["kpis"]["bookings"]["value"], 2)
        self.assertEqual((after["next_booking"]["equipment"][:6], after["next_booking"]["status"]), ("Tablet", "Awaiting approval"))


class LoanWorkflowTests(AppTestCase):
    """Workflow 3: committee issues an item -> stock, loans, borrower dashboard and reports all change -> return restores it."""

    GEOMETRY = 9

    def move(self, committee, kind, quantity, borrower="L-3001", **extra):
        body = {"movement_type": kind, "item_id": self.GEOMETRY, "borrower_id": borrower, "quantity": quantity, "movement_date": self.day(0)}
        if kind == "issue":
            body["due_date"] = self.day(10)
        return committee.post("/api/movements", json={**body, **extra})

    def stock(self, client):
        return next(i for i in self.json(client.get("/api/resources"))["items"] if i["id"] == self.GEOMETRY)["stock"]

    def test_issue_and_return_round_trip(self):
        committee, learner = self.sign_in("ltsm"), self.sign_in("learner")
        self.assertEqual(self.stock(learner), 20)
        self.assertIn("Lwazi Mthembu", self.json(self.move(committee, "issue", 2), 201)["message"])
        self.assertEqual(self.stock(learner), 18)
        dash = self.json(learner.get("/api/dashboard/user"))
        self.assertEqual((dash["kpis"]["issued"]["value"], dash["kpis"]["issued"]["note"], dash["loans"][0]["item"]), (2, "Nothing due soon", "Geometry Set"))
        self.assertEqual(dash["loans"][0]["quantity"], 2)
        self.assertIn("Lwazi Mthembu", [loan["borrower"] for loan in self.json(committee.get("/api/loans"))["items"]])

        self.json(self.move(committee, "return", 1), 201)                                 # partial return
        self.assertEqual((self.stock(learner), self.json(learner.get("/api/dashboard/user"))["kpis"]["issued"]["value"]), (19, 1))
        self.json(self.move(committee, "return", 1), 201)
        self.assertEqual(self.stock(learner), 20)
        self.assertEqual(self.json(learner.get("/api/dashboard/user"))["loans"], [])

    def test_cannot_issue_more_than_is_in_stock_or_return_what_was_never_lent(self):
        committee = self.sign_in("ltsm")
        self.assertEqual(self.move(committee, "issue", 21).status_code, 409)
        self.assertEqual(self.move(committee, "return", 1, borrower="nobody").status_code, 409)
        self.move(committee, "issue", 2)
        self.assertEqual(self.move(committee, "return", 3).status_code, 409)
        self.assertEqual(self.stock(committee), 18)

    def test_stock_levels_feed_the_low_stock_kpi_and_the_report(self):
        committee = self.sign_in("ltsm")
        kpi = lambda: self.json(committee.get("/api/dashboard/committee"))["kpis"]["low_stock"]["value"]
        self.assertEqual(kpi(), 2)
        self.assertIn("69 of 73 units are available", self.json(committee.get("/api/reports"))["summary"][0]["finding"])
        self.move(committee, "issue", 12)                                                  # 20 -> 8, below the reorder level of 10
        self.assertEqual(kpi(), 3)
        report = self.json(committee.get("/api/reports"))
        self.assertIn("57 of 73 units are available", report["summary"][0]["finding"])
        self.assertIn("2 stationery items", report["summary"][1]["finding"])
        stationery = next(c for c in report["categories"] if c["category"] == "Stationery")
        self.assertEqual((stationery["low_stock"], stationery["condition"]), (2, "Review stock"))
        names = [i["name"] for i in self.json(committee.get("/api/dashboard/committee"))["low_stock"]]
        self.assertEqual(names[0], "Mathematics · Grade 7")                               # most urgent first

    def test_overdue_and_due_soon_loans_are_flagged_for_the_borrower(self):
        teacher = self.sign_in("teacher")
        dash = self.json(teacher.get("/api/dashboard/user"))
        self.assertEqual([(l["item"], l["status"]) for l in dash["loans"]], [("Classroom Projector", "Due soon"), ("Natural Sciences · Grade 8", "On loan")])
        self.assertEqual(dash["kpis"]["issued"], {"value": 2, "note": "1 return due soon"})


class MaintenanceAndInventoryTests(AppTestCase):
    def test_logging_an_issue_updates_the_summary_counts(self):
        committee = self.sign_in("ltsm")
        before = self.json(committee.get("/api/maintenance"))["summary"]
        self.assertEqual((before["open"], before["in_repair"], before["out_of_service"]), (0, 1, 1))
        self.json(committee.post("/api/maintenance", json={"equipment": "Projector", "reported_by": "Nomsa", "priority": "High", "date": self.day(0), "description": "Lamp flickers badly"}), 201)
        after = self.json(committee.get("/api/maintenance"))
        self.assertEqual(after["summary"]["open"], 1)
        self.assertEqual((after["items"][0]["item"], after["items"][0]["status"]), ("Projector", "Open"))

    def test_new_inventory_item_reaches_every_view(self):
        committee, teacher = self.sign_in("ltsm"), self.sign_in("teacher")
        self.json(committee.post("/api/inventory", json={"item_name": "Glue sticks", "category": "Stationery", "quantity": 40, "reorder_level": 10}), 201)
        self.assertEqual(committee.post("/api/inventory", json={"item_name": "glue STICKS", "category": "Stationery", "quantity": 1, "reorder_level": 1}).status_code, 409)
        self.assertEqual([i["name"] for i in self.json(teacher.get("/api/resources?q=glue"))["items"]], ["Glue sticks"])
        self.assertEqual(self.json(committee.get("/api/dashboard/committee"))["kpis"]["inventory"]["value"], 69 + 40)
        self.assertEqual(len(self.json(committee.get("/api/inventory?category=Stationery"))["items"]), 4)

    def test_search_matches_names_descriptions_and_ignores_case(self):
        teacher = self.sign_in("teacher")
        names = lambda q: [i["name"] for i in self.json(teacher.get("/api/resources", query_string={"q": q}))["items"]]
        self.assertEqual(names("PROJECTOR"), ["Classroom Projector"])
        self.assertEqual(names("hdmi"), ["Classroom Projector"])
        self.assertEqual(names("zzzz"), [])


class TemplateIntegrityTests(AppTestCase):
    """Every file and page the templates point to must exist (these caught a missing stylesheet)."""

    def templates(self):
        return sorted((Path(__file__).resolve().parent.parent / "Templates").glob("*.html"))

    def test_every_static_file_a_template_loads_exists(self):
        root = Path(__file__).resolve().parent.parent
        referenced = {(t.name, m) for t in self.templates() for m in re.findall(r"filename='([^']+)'", t.read_text(encoding="utf-8"))}
        self.assertTrue(referenced, "no static references found - the pattern is probably wrong")
        for template, filename in referenced:
            with self.subTest(template=template, file=filename):
                self.assertTrue((root / "static" / filename).is_file(), f"{template} loads static/{filename}, which does not exist")

    def test_every_page_link_leads_to_a_real_page(self):
        pages = self.app_module.PUBLIC_PAGES | self.app_module.USER_PAGES | self.app_module.COMMITTEE_PAGES
        for template in self.templates():
            for href in re.findall(r'href="([^"#]+\.html)"', template.read_text(encoding="utf-8")):
                with self.subTest(template=template.name, href=href):
                    self.assertIn(href[:-5], pages, f"{template.name} links to {href}, which is not a routed page")

    def test_every_script_a_page_loads_is_served(self):
        client = self.client
        for template in self.templates():
            for name in re.findall(r"filename='(js/[^']+)'", template.read_text(encoding="utf-8")):
                with self.subTest(template=template.name, script=name):
                    self.assertEqual(client.get(f"/static/{name}").status_code, 200)

    def test_every_page_renders_for_a_signed_in_user(self):
        committee = self.sign_in("ltsm")
        for page in sorted(self.app_module.PUBLIC_PAGES | self.app_module.USER_PAGES | self.app_module.COMMITTEE_PAGES):
            with self.subTest(page=page):
                self.assertEqual(committee.get(f"/{page}.html").status_code, 200)


if __name__ == "__main__":
    unittest.main()
