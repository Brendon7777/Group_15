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

Teacher/learner and LTSM dashboards and management pages now read and write resources, requests, bookings, loans, and maintenance issues through MySQL. The resource catalogue is available at `view-resources.html` and `resource.html`; equipment can be booked directly from its catalogue row, while the main `request-resources.html` page is the hub for requesting items and opening the equipment booking flow. Anyone can submit a resource suggestion at `suggest-resource.html`, anonymously or with a name; LTSM Committee Members review suggestions in the inventory page. LTSM account management uses the `users` table. On `manage-inventory.html`, the Adjust Inventory dropdown is populated from the database with each item's name, category, available stock, reorder level, and status; adjustments add or remove available stock without changing quantity owned, and cannot reduce stock below zero. Every manual adjustment requires a reason, and manual changes plus issues and returns are recorded in the `inventory_adjustment` audit table with the acting user. The inventory page shows the latest 100 audit records. Available stock is also deducted when an LTSM records an actual issue and added back when they record a return on `issue-return.html`; submitting or approving a request alone does not change stock. The LTSM-only inventory forecast is at `inventory-summary.html`; it reads current stock and prices from `resource` and demand history from `consumable_demand_history`, and does not place orders or modify stock. Valid resources are still forecast when another resource has missing or malformed history; the summary lists the affected records and required corrections. Each six-month resource needs six monthly demand values over six complete months, and each annual resource needs three annual values over 36 complete months. The initializer migrates recognized sample data and backfills existing issue/return movements into the audit table without resetting the database.

The request and response shapes are documented in `API_CONTRACT.md`.

**Tests, deployment and documentation (Task 4A)**

- Run all tests: `python -m unittest discover -s tests -v` (see `docs/TEST_REPORT.md` for results, bugs found and the usability test script).
- Configuration: copy `.env.example` to `.env`.
- Deployment (Procfile / Docker), health check, troubleshooting: `docs/RUNBOOK.md`.
