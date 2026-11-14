# LTSM Portal – Test Report (Task #9: unit, integration and usability testing)

Scope: the Flask API (`app.py`), the `fetch()` front end (`static/js/`), the Jinja pages (`Templates/`) and the supply-chain calculations (`inventory_model.py`).
Status when written: **82 automated tests, all passing**; 9 bugs found and fixed, 1 open (low).

## 1. How to run

```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
```

Only the Python standard library is needed for the unit and integration tests. Browser tests start a real Flask server and drive headless Chromium; they are skipped (not failed) if Chromium is missing. The same command runs on every push through `.github/workflows/tests.yml`.

## 2. Test plan and results

| Level | File | Tests | What it proves |
| --- | --- | ---: | --- |
| Unit | `tests/test_unit_helpers.py` | 17 | Input validation rules (text, numbers, e-mail, dates, times), stock / availability / loan / priority rules, school-timezone clock, production configuration |
| Unit | `tests/test_unit_inventory_model.py` | 12 | Every supply-chain function against hand-calculated values (mean, standard deviation, safety stock, order quantity, risk thresholds, cost, second-cycle carry-over) |
| Integration | `tests/test_integration_api.py` | 37 | Sessions and cookies, every endpoint's sign-in and role rule, validation errors, the four workflows through the real HTTP layer, KPI and report consistency, template links / static files / scripts exist |
| Integration (browser) | `tests/test_browser_workflows.py` | 10 | Three end-to-end workflows between two signed-in people, a stale-decision conflict, loading / empty / error / retry states, session expiry, double-submit protection, HTML injection |
| Usability (browser) | `tests/test_browser_usability.py` | 6 | Accessibility audit of all 13 pages, no sideways scrolling on a 375 px phone, keyboard-only sign-in, visible focus, clear sign-in errors, password check before sending |

### The end-to-end workflows covered

1. **Resource request:** teacher submits → committee sees it with a priority and accepts on the dashboard → teacher's *My requests* shows *Approved*; committee KPI falls from 4 to 3. A second committee member acting on the same request is told it was already decided.
2. **Equipment booking:** teacher books a tablet set → *Awaiting approval* → committee confirms → teacher's dashboard shows it *Confirmed*. Overlapping bookings are refused; declining frees the slot.
3. **Issue and return:** committee issues an item → stock drops in the catalogue, the loan shows on the borrower's dashboard (KPI, table, count) and in reports → return restores everything; partial returns work.
4. **Maintenance:** logging an issue updates the open / in-repair / out-of-service counts.

## 3. Bugs found

| ID | Severity | Bug | Found by | Status |
| --- | --- | --- | --- | --- |
| BUG-01 | High | `register.html` had no `method`, so if the script failed to load the password would be sent in the web address (GET) | Code review | Fixed: `method="post"` added |
| BUG-02 | Low | `login.html` loads `static/css/style.css`, which did not exist (404 on every sign-in page load) | Browser log, `TemplateIntegrityTests` | Fixed: file added (placeholder) |
| BUG-03 | Medium | README told users to open pages with Live Server, which cannot render Jinja or reach the API | Manual run-through | Fixed: README and runbook |
| BUG-04 | Medium | Hard-coded dashboard numbers contradicted each other (e.g. "Items issued to you: 4" above a table saying "3 active items") | Manual review | Fixed: all KPIs computed from the same data |
| BUG-05 | Medium | Date checks used the server's clock. On a UTC server, between 00:00 and 02:00 SA time a valid "today" was rejected as "in the future" | `test_today_uses_the_school_timezone...` | Fixed: `APP_TIMEZONE` clock |
| BUG-06 | Low | `inventory_model.py`: an empty demand list raises a raw `ZeroDivisionError` | `test_known_limitation_empty_history...` | **Open.** The file is not part of this task's changes; suggest a clear `ValueError` |
| BUG-07 | High | A new request stored its needed-by date as a Python date object; the committee request list then crashed with HTTP 500 for everyone | `RequestWorkflowTests` | Fixed: stored as ISO text |
| BUG-08 | Low | Unknown page names redirected to sign-in when signed out but returned 404 when signed in | `PermissionTests` | Fixed: unknown pages are always 404 |
| BUG-09 | Medium | Report page: *Try again* inside one second re-used the failed response, and retrying one table left the other two broken | `test_every_report_table_has_an_error_state...` | Fixed: failures are never cached; one retry reloads all three tables |
| BUG-10 | Low | User dashboard scrolled sideways by 3 px on a 375 px phone (the *Bookable* badge did not fit its card). Present in the original page | `test_no_page_scrolls_sideways_on_a_phone` | Fixed: card footer wraps |

## 4. Usability findings

Automated checks that **passed on all 13 pages:** page language and title, exactly one `<h1>`, a `<main>` landmark, every form field has a label, every button and link has text, no images without alt text, no duplicate ids, no dead `#` links. Errors are announced (`role="alert"`), successes use `role="status"`, buttons are disabled while saving (no double submit), nothing the user typed is lost after an error, and the sign-in form works with the keyboard alone with a visible focus indicator.

Not covered by automation, so please run the short session below with 3–5 people (teachers or classmates) and record the results.

| # | Task (read aloud, do not explain the screen) | Success looks like | Time | Problems / quotes |
| --- | --- | --- | --- | --- |
| 1 | "Find out whether a projector is available." | Finds *Browse resources*, searches or filters | | |
| 2 | "Ask for 30 science workbooks by next Friday." | Submits the request form without help | | |
| 3 | "Has your request been approved?" | Opens *My requests*, reads the status | | |
| 4 | "Reserve the tablet set for Monday 09:00–10:00." | Completes the booking form | | |
| 5 | *(committee)* "Approve the newest request." | Uses Accept on the dashboard | | |
| 6 | *(committee)* "Lend a geometry set to learner L-3001." | Completes the issue form | | |

Record for each person: task completed (yes / needed help / no), wrong turns, and one thing they found confusing. Fix anything that two or more people trip over.

## 5. Not tested / risks

- Only Chromium was used; Firefox and Safari were not.
- Screen-reader behaviour and colour contrast were not measured.
- The data is in memory, so concurrency across several server workers and database behaviour are untested. They need new tests when MySQL is connected.
- Load and security testing (rate limiting, password-guessing protection) were not performed; none exists yet.
- The `Dockerfile`, `Procfile` and GitHub Actions workflow were written to standard patterns but not executed in the environment where this report was produced. Run them once and fix anything that differs on your machine.
