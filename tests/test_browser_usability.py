"""Usability and accessibility checks run on every page, on a desktop and a phone-sized screen, plus keyboard-only use of the sign-in form."""
import unittest

from base import BrowserTestCase, CREDENTIALS, PASSWORD

PUBLIC = ["index", "login", "register"]
USER = ["user-dashboard", "view-resources", "request-resources", "my-requests", "book-equipment"]
COMMITTEE = ["ltsm-dashboard", "manage-inventory", "issue-return", "maintenance", "reports"]

PAGE_AUDIT = """() => {
  const problems = [];
  if (!document.documentElement.lang) problems.push("<html> has no lang attribute");
  if (!document.title.trim()) problems.push("page has no <title>");
  const h1 = document.querySelectorAll("h1").length;
  if (h1 !== 1) problems.push(`${h1} <h1> headings (expected 1)`);
  if (!document.querySelector("main")) problems.push("no <main> landmark");
  const nameOf = (el) => {
    if (el.getAttribute("aria-label") || el.getAttribute("aria-labelledby")) return true;
    if (el.id && document.querySelector(`label[for="${el.id}"]`)) return true;
    return !!el.closest("label");
  };
  for (const el of document.querySelectorAll("input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea"))
    if (!nameOf(el)) problems.push(`form field without a label: ${el.id || el.name || el.type}`);
  for (const el of document.querySelectorAll("button, a[href]")) {
    const text = (el.textContent || "").trim() || el.getAttribute("aria-label") || el.getAttribute("title");
    if (!text) problems.push(`button or link without text: ${el.outerHTML.slice(0, 70)}`);
  }
  for (const img of document.querySelectorAll("img:not([alt])")) problems.push(`image without alt: ${img.src}`);
  const ids = [...document.querySelectorAll("[id]")].map((e) => e.id);
  for (const id of new Set(ids.filter((id, i) => ids.indexOf(id) !== i))) problems.push(`duplicate id: ${id}`);
  for (const a of document.querySelectorAll("a[href]")) {
    const href = a.getAttribute("href");
    if (href === "#" || href.startsWith("javascript:")) problems.push(`dead link: ${href}`);
  }
  return problems;
}"""


class UsabilityTests(BrowserTestCase):
    def audit_every_page(self, width, height, check):
        for role, pages in (("teacher", USER), ("ltsm", COMMITTEE)):
            page = self.new_page(width, height)
            self.sign_in_browser(page, role)
            for name in pages:
                page.goto(f"{self.base_url}/{name}.html")
                page.wait_for_load_state("networkidle")
                self.assertEqual(page.locator(".state-row--loading").count(), 0, f"{name} is still loading")
                with self.subTest(page=name):
                    check(page, name)
        anonymous = self.new_page(width, height)
        for name in PUBLIC:
            anonymous.goto(f"{self.base_url}/{name}.html")
            anonymous.wait_for_load_state("networkidle")
            with self.subTest(page=name):
                check(anonymous, name)

    def test_every_page_passes_the_structure_and_labelling_audit(self):
        self.audit_every_page(1280, 900, lambda page, name: self.assertEqual(page.evaluate(PAGE_AUDIT), []))
        self.assert_no_js_errors()

    def test_no_page_scrolls_sideways_on_a_phone(self):
        def check(page, name):
            widths = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
            self.assertLessEqual(widths[0], widths[1], f"{name} is {widths[0]}px wide on a {widths[1]}px screen")
        self.audit_every_page(375, 700, check)

    def test_sign_in_works_with_the_keyboard_alone(self):
        page = self.new_page()
        page.goto(self.base_url + "/login")
        page.focus("#role")
        page.keyboard.press("ArrowDown")                    # the first real option is picked with the arrow keys
        page.keyboard.press("Tab")
        page.keyboard.type(CREDENTIALS["teacher"])
        page.keyboard.press("Tab")
        page.keyboard.type(PASSWORD)
        page.keyboard.press("Enter")                        # Enter submits, no mouse needed
        page.wait_for_url("**/user-dashboard.html")

    def test_failed_sign_in_explains_itself_and_keeps_what_was_typed(self):
        page = self.new_page()
        page.goto(self.base_url + "/login")
        page.select_option("#role", "teacher")
        page.fill("#username", CREDENTIALS["teacher"])
        page.fill("#password", "wrong-password")
        page.click("#login-form button[type=submit]")
        page.wait_for_selector("#login-feedback:not([hidden])")
        self.assertEqual(page.get_attribute("#login-feedback", "role"), "alert")
        self.assertIn("Incorrect", page.inner_text("#login-feedback"))
        self.assertEqual(page.input_value("#username"), CREDENTIALS["teacher"])
        self.assertFalse(page.is_disabled("#login-form button[type=submit]"))

    def test_keyboard_focus_is_visible_on_form_fields_and_buttons(self):
        page = self.new_page()
        page.goto(self.base_url + "/login")
        for selector in ("#username", "#password", "#login-form button[type=submit]"):
            page.focus(selector)
            page.keyboard.press("Shift+Tab"); page.keyboard.press("Tab")          # arrive by keyboard so :focus-visible applies
            look = page.evaluate("(s) => { const c = getComputedStyle(document.querySelector(s)); return [c.outlineStyle, c.outlineWidth, c.boxShadow, c.borderColor]; }", selector)
            visible = look[0] != "none" and look[1] != "0px" or look[2] != "none"
            self.assertTrue(visible, f"{selector} shows no focus indicator: {look}")

    def test_registration_checks_passwords_before_sending_anything(self):
        page = self.new_page()
        sent = []
        page.on("request", lambda r: sent.append(r.url) if "/api/register" in r.url else None)
        page.goto(self.base_url + "/register.html")
        page.fill("#full-name", "Pat Teacher"); page.select_option("#account-type", "teacher"); page.fill("#school-id", "T-7777")
        page.fill("#email", "pat@example.com"); page.fill("#password", "longenough1"); page.fill("#confirm-password", "different1")
        page.click("#register-form button[type=submit]")
        self.assertEqual(sent, [])                                                  # blocked in the browser
        self.assertTrue(page.evaluate("!document.getElementById('confirm-password').validity.valid"))
        page.fill("#confirm-password", "longenough1")
        page.click("#register-form button[type=submit]")
        page.wait_for_url("**/login", timeout=5000)
        self.assertEqual(len(sent), 1)


if __name__ == "__main__":
    unittest.main()
