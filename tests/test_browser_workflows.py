"""Browser tests (headless Chromium, real pages + live Flask server): three end-to-end workflows plus loading, empty and error states."""
import unittest

from base import BrowserTestCase


class WorkflowTests(BrowserTestCase):
    def row(self, page, table, text):
        return page.locator(f"{table} tbody tr", has_text=text)

    def kpi(self, page, key):
        return page.locator(f'[data-kpi="{key}"]').inner_text()

    # ---- workflow 1: resource request -> committee decision -> teacher sees the outcome
    def test_request_workflow(self):
        teacher = self.sign_in_browser(self.page, "teacher")
        teacher.goto(self.base_url + "/request-resources.html")
        teacher.fill("#resource-name", "Chalk boxes")
        teacher.select_option("#category", "Other")
        teacher.fill("#quantity", "6")
        teacher.fill("#needed-by", self.day(1))
        teacher.fill("#purpose", "Needed for the new Grade 5 classroom board")
        teacher.click("#request-form button[type=submit]")
        teacher.wait_for_selector("#request-feedback.form-feedback--success")

        committee = self.sign_in_browser(self.new_page(), "ltsm")
        row = self.row(committee, "#committee-requests-table", "Chalk boxes")
        row.wait_for()
        self.assertIn("High", row.inner_text())                                   # needed tomorrow
        self.assertEqual(self.kpi(committee, "pending_requests"), "4")
        row.locator("button[data-decision=Approved]").click()
        committee.wait_for_selector("#action-feedback.form-feedback--success")
        self.assertIn("approved", committee.inner_text("#action-feedback"))
        committee.wait_for_function("document.querySelector('[data-kpi=pending_requests]').textContent === '3'")
        self.assertEqual(self.row(committee, "#committee-requests-table", "Chalk boxes").count(), 0)

        teacher.goto(self.base_url + "/my-requests.html")
        self.assertIn("Approved", self.row(teacher, "#requests-table", "Chalk boxes").inner_text())
        self.assert_no_js_errors()

    # ---- workflow 2: equipment booking -> committee confirms -> teacher's dashboard shows it confirmed
    def test_booking_workflow(self):
        teacher = self.sign_in_browser(self.page, "teacher")
        teacher.goto(self.base_url + "/book-equipment.html")
        teacher.wait_for_function("document.querySelectorAll('#equipment option').length > 1")
        teacher.select_option("#equipment", label="Tablet Set · 10 devices (1 in stock)")
        teacher.fill("#booking-date", self.day(2))
        teacher.fill("#start-time", "09:00")
        teacher.fill("#end-time", "10:00")
        teacher.fill("#room", "Library")
        teacher.fill("#booking-purpose", "Grade 8 reading project")
        teacher.click("#booking-form button[type=submit]")
        teacher.wait_for_selector("#booking-feedback.form-feedback--success")
        self.assertIn("Awaiting approval", self.row(teacher, "#bookings-table", "Tablet").inner_text())

        committee = self.sign_in_browser(self.new_page(), "ltsm")
        row = self.row(committee, "#committee-bookings-table", "Ayesha Jacobs")
        row.filter(has_text="Tablet").wait_for()
        row.filter(has_text="Tablet").locator("button[data-decision=Confirmed]").click()
        committee.wait_for_selector("#action-feedback.form-feedback--success")
        row.filter(has_text="Tablet").filter(has_text="Confirmed").wait_for()                  # badge replaced the buttons
        self.assertEqual(row.filter(has_text="Tablet").locator("button").count(), 0)

        teacher.goto(self.base_url + "/user-dashboard.html")
        teacher.wait_for_selector("#next-booking h3")
        self.assertIn("Tablet Set", teacher.inner_text("#next-booking"))
        self.assertIn("Confirmed", teacher.inner_text("#next-booking"))
        self.assert_no_js_errors()

    # ---- workflow 3: committee issues an item -> borrower sees it on the dashboard -> committee records the return
    def test_issue_and_return_workflow(self):
        committee = self.sign_in_browser(self.page, "ltsm")
        learner = self.sign_in_browser(self.new_page(), "learner")
        learner.wait_for_selector(".issued-items-table tbody .state-row--empty")           # nothing issued yet: empty state

        committee.goto(self.base_url + "/issue-return.html")
        committee.wait_for_function("document.querySelectorAll('#inventory-item option').length > 1")
        committee.select_option("#movement-type", "issue")
        committee.select_option("#inventory-item", label="Geometry Set (20 in stock)")
        committee.fill("#borrower-id", "L-3001")
        committee.fill("#movement-quantity", "2")
        committee.fill("#due-date", self.day(10))
        committee.click("#movement-form button[type=submit]")
        committee.wait_for_selector("#movement-feedback.form-feedback--success")
        self.assertIn("Geometry Set", self.row(committee, "#loans-table", "Lwazi Mthembu").inner_text())

        learner.reload()
        learner.wait_for_function("document.querySelector('[data-kpi=issued]').textContent === '2'")
        self.assertIn("Geometry Set ×2", learner.inner_text(".issued-items-table"))
        self.assertEqual(learner.inner_text("#issued-count"), "1 active item")

        committee.select_option("#movement-type", "return")
        committee.select_option("#inventory-item", label="Geometry Set (18 in stock)")
        committee.fill("#borrower-id", "L-3001")
        committee.fill("#movement-quantity", "2")
        committee.click("#movement-form button[type=submit]")
        committee.wait_for_selector("#movement-feedback.form-feedback--success")
        learner.reload()
        learner.wait_for_selector(".issued-items-table tbody .state-row--empty")
        self.assertEqual(self.kpi(learner, "issued"), "0")
        self.assert_no_js_errors()

    # ---- two committee members act on the same request: the second one is told, and the list refreshes
    def test_stale_decision_is_explained_and_the_list_refreshes(self):
        first = self.sign_in_browser(self.page, "ltsm")
        second = self.sign_in_browser(self.new_page(), "ltsm")
        for page in (first, second):
            self.row(page, "#committee-requests-table", "Calculator set").wait_for()
        self.row(first, "#committee-requests-table", "Calculator set").locator("button[data-decision=Declined]").click()
        first.wait_for_selector("#action-feedback.form-feedback--success")
        self.row(second, "#committee-requests-table", "Calculator set").locator("button[data-decision=Approved]").click()
        second.wait_for_selector("#action-feedback.form-feedback--error")
        self.assertIn("already declined", second.inner_text("#action-feedback"))
        second.wait_for_function("!document.querySelector('#committee-requests-table').innerText.includes('Calculator set')")


class StateTests(BrowserTestCase):
    """Loading, empty and error states, including recovery with the Try again button."""

    def test_loading_empty_and_error_states_on_the_resource_list(self):
        page = self.sign_in_browser(self.page, "teacher")
        held = []
        page.route("**/api/resources*", lambda route: held.append(route))
        page.goto(self.base_url + "/view-resources.html")
        page.wait_for_selector("#resource-list .state-row--loading")                         # loading state while the request is pending
        self.assertEqual(page.get_attribute("#resource-list tbody", "aria-busy"), "true")
        held[0].continue_()
        page.wait_for_function("document.querySelectorAll('#resource-list tbody tr:not(.state-row)').length === 9")
        page.unroute("**/api/resources*")

        page.fill("#resource-search", "zzzz")                                                # empty state
        page.wait_for_selector("#resource-list .state-row--empty")
        self.assertIn("No resources match", page.inner_text("#resource-list tbody"))

        page.route("**/api/resources*", lambda route: route.fulfill(status=500, json={"error": "Database unavailable"}))
        page.fill("#resource-search", "projector")                                           # error state shows the server's message
        page.wait_for_selector("#resource-list .state-row--error")
        self.assertIn("Database unavailable", page.inner_text("#resource-list tbody"))
        page.unroute("**/api/resources*")
        page.click(".state-retry")                                                           # recovery
        page.wait_for_function("document.querySelectorAll('#resource-list tbody tr:not(.state-row)').length === 1")
        self.assert_no_js_errors()

    def test_dashboard_shows_dashes_and_a_retry_when_the_server_is_down(self):
        page = self.sign_in_browser(self.page, "teacher")
        page.route("**/api/dashboard/user", lambda route: route.abort())
        page.reload()
        page.wait_for_selector("#dashboard-feedback:not([hidden])")
        self.assertIn("Could not reach the server", page.inner_text("#dashboard-feedback"))
        self.assertEqual(page.locator('[data-kpi="issued"]').inner_text(), "–")
        page.unroute("**/api/dashboard/user")
        page.click("#dashboard-feedback .state-retry")
        page.wait_for_function("document.querySelector('[data-kpi=available_resources]').textContent === '69'")
        self.assertTrue(page.locator("#dashboard-feedback").is_hidden())

    def test_every_report_table_has_an_error_state_and_recovers(self):
        page = self.sign_in_browser(self.page, "ltsm")
        page.route("**/api/reports", lambda route: route.fulfill(status=503, json={"error": "Report service is busy"}))
        page.goto(self.base_url + "/reports.html")
        page.wait_for_function("document.querySelectorAll('.state-row--error').length === 3")
        page.unroute("**/api/reports")
        page.click(".insights-table .state-retry")                                           # one retry reloads all three tables
        page.wait_for_function("document.querySelectorAll('.state-row').length === 0")
        self.assertIn("69 of 73 units are available", page.inner_text(".insights-table"))
        self.assertIn("Textbooks", page.inner_text("#category-summary-table"))
        self.assertIn("In review", page.inner_text(".status-table"))

    def test_form_buttons_are_disabled_while_saving_and_errors_are_announced(self):
        page = self.sign_in_browser(self.page, "ltsm")
        page.goto(self.base_url + "/maintenance.html")
        page.fill("#equipment-name", "Projector"); page.fill("#reported-by", "Nomsa"); page.select_option("#issue-priority", "High")
        page.fill("#issue-date", self.day(0)); page.fill("#issue-description", "Lamp flickers and switches off")
        held = []
        page.route("**/api/maintenance", lambda route: held.append(route) if route.request.method == "POST" else route.continue_())
        page.click("#maintenance-form button[type=submit]")
        page.wait_for_function("document.querySelector('#maintenance-form button[type=submit]').disabled")
        self.assertEqual(page.inner_text("#maintenance-form button[type=submit]"), "Logging…")
        held[0].fulfill(status=400, json={"error": "Description must be 10–500 characters.", "fields": {"description": "x"}})
        page.wait_for_selector("#maintenance-feedback.form-feedback--error")
        self.assertEqual(page.get_attribute("#maintenance-feedback", "role"), "alert")
        self.assertEqual(page.get_attribute("#issue-description", "aria-invalid"), "true")
        self.assertEqual(page.input_value("#equipment-name"), "Projector")                   # nothing the user typed is lost
        self.assertFalse(page.is_disabled("#maintenance-form button[type=submit]"))

    def test_expired_session_sends_the_user_back_to_sign_in(self):
        page = self.sign_in_browser(self.page, "teacher")
        page.goto(self.base_url + "/view-resources.html")
        page.wait_for_selector("#resource-list tbody tr:not(.state-row)")
        page.context.clear_cookies()
        page.fill("#resource-search", "projector")
        page.wait_for_url("**/login")


class SecurityBrowserTests(BrowserTestCase):
    def test_user_supplied_html_is_shown_as_text_not_executed(self):
        page = self.sign_in_browser(self.page, "ltsm")
        page.goto(self.base_url + "/manage-inventory.html")
        page.wait_for_selector("#inventory-table tbody tr:not(.state-row)")
        payload = "<img src=x onerror=window.__pwned=1>"
        page.fill("#item-name", payload); page.select_option("#item-category", "Other")
        page.fill("#item-quantity", "5"); page.fill("#reorder-level", "1")
        page.click("#inventory-form button[type=submit]")
        page.wait_for_selector("#inventory-feedback.form-feedback--success")
        page.wait_for_function("document.querySelectorAll('#inventory-table tbody tr:not(.state-row)').length === 10")
        self.assertIn(payload, page.inner_text("#inventory-table"))
        self.assertEqual(page.locator("#inventory-table img").count(), 0)
        self.assertIsNone(page.evaluate("window.__pwned"))


if __name__ == "__main__":
    unittest.main()
