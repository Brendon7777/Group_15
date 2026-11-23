Group 15 – LTSM Portal

**Project Description**

The LTSM Portal is a web-based platform proposed to improve the management, allocation and distribution of Learning and Teaching Support Materials at primary schools. It aims to improve resource visibility, streamline bookings and requests, track inventory, and support management reporting.

The current project focuses on the front-end interface, including page layouts, navigation and forms.


**Group Members**

Brendon Sithole

23547309


Tebogo Napyane

20553596


Phiwayinkhosi Nxumalo

22780450


Kimberleigh Hartley

19008423



**Technologies**

HTML

CSS

Jinja templates

Visual Studio Code

Git and GitHub



**Installation and Setup**

Clone the repository:

git clone <repository-url>

Open the project folder in Visual Studio Code.

Install the Live Server extension if it is not already installed.

Open the relevant HTML page.

Right-click the page and select Open with Live Server.

The page will open in your default web browser.

Note: The current version focuses on the front end. Features requiring back-end processing or database integration are not necessarily functional.




**Repository**

Repository name: Group-15


**Running the portal with the Flask API (Task 3A)**

The pages now call a Flask JSON API with JavaScript `fetch()`, so they must be served by Flask (Live Server cannot render the Jinja templates or reach the API).

```
python -m venv .venv
.venv\Scripts\activate        (Windows)   |   source .venv/bin/activate   (macOS/Linux)
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 and sign in with a demo account (password for all: `Password123!`):

| Role | Username |
| --- | --- |
| Teacher | g2.teacher1@example.com |
| Learner | learner01@example.com |
| LTSM Committee Member | ltsm01@example.com |

Database setup and account persistence:

```
python init_db.py
```

This creates missing tables, including `resource_suggestion`, applies the user-account status migration, safely corrects recognized legacy sample inventory histories, and loads sample data only when the resource table is empty. Registration and login use the MySQL `users` table. LTSM Committee Members can manage accounts at `manage-users.html`; deactivation blocks sign-in while retaining account history. Do not use `python init_db.py --reset` unless you intend to drop the project tables and their data.

Teacher/learner and LTSM dashboards and management pages now read and write resources, requests, bookings, loans, and maintenance issues through MySQL. The resource catalogue is available at `view-resources.html` and `resource.html`; it displays item photos matched by resource name with a category-photo fallback, and the same photos appear in the LTSM inventory catalogue. Equipment can be booked directly from its catalogue row, while the main `request-resources.html` page is the hub for requesting items and opening the equipment booking flow. LTSM Committee Members can review all past and upcoming equipment reservations, filter them by status, approve or decline pending bookings, cancel confirmed future bookings, and view day, week, or month calendars at `manage-bookings.html`; overlapping bookings are limited to the currently available equipment quantity and are checked again when confirming. The LTSM dashboard retains a compact upcoming-bookings panel with a link to the full booking list. Anyone can submit a resource suggestion at `suggest-resource.html`, anonymously or with a name; LTSM Committee Members review suggestions in the inventory page. LTSM account management uses the `users` table. LTSM request decisions are managed at `request-management.html`: the committee checks current available stock, allocates and reserves the full requested quantity, and schedules a collection slot before marking a request ready. Marking it fulfilled records an issue in the circulation history and deducts stock; the issued items then appear in `issue-return.html` for a later return. Declined, pending, ready, and fulfilled requests are filterable on the management page, while requesters can track collection details and status on `my-requests.html`. On `manage-inventory.html`, LTSM Committee Members can add and edit inventory records, set descriptions, units and storage locations, and categorize resources as textbooks, stationery, consumables, equipment or other. Receive stock increases available and owned quantities; removals and damaged, lost or obsolete write-offs reduce available stock and are recorded with a reason, actor and timestamp. Stock allocated to requests is excluded from availability and protected from manual removal and other issues. The page shows the latest 100 audit records, including received stock, write-offs and issue/return movements. The LTSM-only inventory forecast is at `inventory-summary.html`; it reads current stock and prices from `resource` and demand history from `consumable_demand_history`, and does not place orders or modify stock. Valid resources are still forecast when another resource has missing or malformed history; the summary lists the affected records and required corrections. Each six-month resource needs six monthly demand values over six complete months, and each annual resource needs three annual values over 36 complete months. The initializer migrates inventory locations and request-allocation fields, adds the Fulfilled status, links existing requests to matching inventory items, corrects recognized sample data, and backfills existing issue/return movements into the audit table without resetting the database.
Resource requests display their submission timestamp in the LTSM management queue, oldest first. Approvals are enforced first-come, first-served per inventory item; an earlier pending request must be decided before a later request can be approved. The database initializer adds `submitted_at` to existing installations; older requests use their original submission date with request ID as the tie-breaker because their exact historical time is unavailable.

Equipment bookings require a 20-minute gap between uses of the same item. The buffer is checked both when a booking is requested and again when the committee confirms it, including bookings on adjacent dates.
The booking form shows each equipment item's available count and recorded storage location, if set; the room field records where the requester will use it.

The request and response shapes are documented in `API_CONTRACT.md`.

Email response notifications:

- Copy `.env.example` to `.env` and configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and, if needed, `SMTP_USE_TLS` or `SMTP_USE_SSL`.
- After an LTSM member approves or declines a resource request, fulfills a request, or confirms/declines/cancels a booking, the requester receives an email at the address stored on their account.
- Email delivery is best-effort: if SMTP is not configured or delivery fails, the portal notification and database status still complete successfully.

The shared navigation displays persistent unread notification badges for LTSM members when new resource requests arrive, and for requesters when resource requests or equipment bookings are approved, declined, or cancelled. Each relevant module shows its notification history; opening the module marks its notifications as read without deleting the history. Notification writes are committed with the request or booking decision.

Request collection points are stored separately from inventory storage locations. LTSM selects an active point when approving a request; the chosen point and scheduled time are saved with that request and included in the requester’s status update and approval notification. The initializer adds the collection-location table and nullable request link without resetting existing data, and seeds “Storage Room 01” and “Printer Room 34” as initial options.

The LTSM circulation desk at `issue-return.html` issues resources only to active, registered teachers and learners. Each issue records its original quantity, recipient, issue date, expected return date and recording staff member. Returns and lost/damaged reports are appended as separate events linked to the exact issue; outstanding quantities are calculated from those events, and the recent history can be searched by borrower or item. Return events restore available stock, while lost/damaged events reduce the owned quantity and appear in the inventory audit trail. The initializer adds the tracking fields without resetting existing data; existing active loan quantities are preserved as their migration-time outstanding balance, while new events receive exact issue links.

**Tests, deployment and documentation (Task 4A)**

- Run all tests: `python -m unittest discover -s tests -v` (see `docs/TEST_REPORT.md` for results, bugs found and the usability test script).
- Configuration: copy `.env.example` to `.env`.
- Deployment (Procfile / Docker), health check, troubleshooting: `docs/RUNBOOK.md`.
