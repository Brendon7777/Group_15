# LTSM Portal – Runbook

How to set up, run, test, deploy and look after the portal. Written for the group (Tasks #7–#9).

## 1. What is running

| Part | What it is |
| --- | --- |
| `app.py` | Flask application: serves the Jinja pages in `Templates/` and the JSON API under `/api` (see `API_CONTRACT.md`) |
| `static/js/*.js` | The `fetch()` code that connects each page to the API |
| Data | **Kept in memory** inside `app.py` (sample data). It resets whenever the server restarts. The MySQL layer (`staff.sql`) is not connected yet |
| `inventory_model.py` | Separate supply-chain calculation script; run on its own, it writes `inventory_summary.html` |

## 2. Run it on your computer

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

macOS / Linux: `source .venv/bin/activate` and `cp .env.example .env` instead.

Open http://127.0.0.1:5000. Demo sign-ins (password `Password123!`): `g2.teacher1@example.com` (teacher), `learner01@example.com` (learner), `ltsm01@example.com` (LTSM committee).

> The pages must be opened through Flask. The VS Code *Live Server* extension cannot run the Jinja templates or reach the API.

## 3. Configuration (`.env`)

| Setting | Meaning | Default |
| --- | --- | --- |
| `APP_ENV` | `development` or `production`. Production **requires** `SECRET_KEY` and sends cookies only over HTTPS | `development` |
| `SECRET_KEY` | Signs the login cookie. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` | dev-only value |
| `APP_TIMEZONE` | Timezone used for "today" | `Africa/Johannesburg` |
| `HOST`, `PORT` | Where `python app.py` listens | `127.0.0.1`, `5000` |
| `FLASK_DEBUG` | `1` = auto-reload (your computer only) | `0` |

Never commit `.env`. It is listed in `.gitignore`.

## 4. Run the tests

```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium      # once, for the browser tests
python -m unittest discover -s tests -v    # everything (about a minute)
```

Faster subsets: `-p "test_unit*.py"` (unit), `-p "test_integration*.py"` (API), `-p "test_browser*.py"` (needs Chromium; skipped automatically if it is missing). Details and results: `docs/TEST_REPORT.md`.

## 5. Deploy

Use **one worker**. The sample data is in each worker's memory; with several workers every request could show different data. Raise the worker count only after the database is connected.

**Option A – a platform that reads a `Procfile` (Render, Railway, Heroku-style)**
1. Create a web service from the GitHub repository. Build command: `pip install -r requirements.txt`. Start command comes from `Procfile`.
2. Set environment variables: `APP_ENV=production`, `SECRET_KEY=<long random value>`. (`PORT` is provided by the platform.)
3. Set the health-check path to `/health`.

**Option B – Docker**
```bash
docker build -t ltsm-portal .
docker run -p 8000:8000 -e SECRET_KEY=<long random value> ltsm-portal
```
The image runs as a non-root user and has a built-in health check.

HTTPS is required in production (the cookie is marked `Secure`); hosting platforms provide it automatically.

## 6. Check that it is healthy

1. `GET /health` returns `{"status":"ok", ...}`.
2. Open `/login`, sign in as the committee demo user, and confirm the dashboard KPI cards show numbers (not `–`).
3. Run `python -m unittest discover -s tests -p "test_integration*.py"` against the same code before releasing.

## 7. Routine operations

| Task | How |
| --- | --- |
| Restart | Restart the service. In-memory data returns to the sample data |
| See errors | Platform log viewer, or `docker logs <container>`. Every API error is also returned as JSON `{"error": ...}` |
| Sign everyone out | Change `SECRET_KEY` and restart |
| Roll back | Redeploy the previous Git commit (`git revert <commit>` then push, or redeploy the earlier build in the platform) |

## 8. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| Page shows raw `{{ ... }}` or looks unstyled | Opened with Live Server or by double-clicking. Start `python app.py` and use http://127.0.0.1:5000 |
| `RuntimeError: SECRET_KEY must be set` | `APP_ENV=production` without a key. Set `SECRET_KEY` |
| `ZoneInfoNotFoundError` | `tzdata` is missing (common on Windows). `pip install -r requirements.txt` |
| Every page redirects to `/login` | Session expired or the secret key changed. Sign in again |
| Tables show "Could not reach the server" | The server stopped, or the browser is offline. Restart and click **Try again** |
| Data I added has vanished | Expected: data is in memory and resets on restart |
| Different data on each refresh in production | More than one worker. Use `--workers 1` |
| Browser tests are skipped | Chromium missing: `python -m playwright install chromium` |
| `git push` rejected with 403 | Your GitHub account is not a collaborator. Ask the repository owner, or fork and open a pull request |

## 9. Known limitations (read before real use)

- **Demo accounts with a published password exist**, and registration cannot create committee accounts. Replace both with the database before real users touch it (the app logs a warning in production).
- No database yet: data resets on restart and cannot be shared between several workers.
- No rate limiting on sign-in and no password reset.
- Requests and bookings cannot be edited or cancelled after submitting.
