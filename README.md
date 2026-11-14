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

`app.py` currently keeps its data in memory (it resets when the server restarts). Replace the list operations inside each endpoint with SQL queries when the database layer is ready. The request and response shapes are documented in `API_CONTRACT.md`.

**Tests, deployment and documentation (Task 4A)**

- Run all tests: `python -m unittest discover -s tests -v` (see `docs/TEST_REPORT.md` for results, bugs found and the usability test script).
- Configuration: copy `.env.example` to `.env`.
- Deployment (Procfile / Docker), health check, troubleshooting: `docs/RUNBOOK.md`.
