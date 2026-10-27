# Namat

Namat (نمط, "pattern") is a private headache and migraine tracker. People record their headache episodes, sleep and daily factors, see their own patterns, and take a clear medical report (in English or Arabic, as a PDF) to their doctor.

Namat describes what was recorded. It doesn't diagnose, doesn't claim that anything causes headaches, and doesn't give treatment advice.

## Features

- **Accounts:** registration and login (Argon2id passwords, short-lived JWT access tokens kept only in memory).
- **Headache episodes:** start and end, peak intensity, pain location, aura, symptoms, medication with dose and recorded relief, and notes. Includes a history list and an edit form.
- **Sleep and daily factors:** sleep times, quality and awakenings, plus stress, caffeine, water, alcohol, exercise, skipped meals and menstruation. "Not recorded" is kept apart from 0 or "no".
- **Dashboard:** summary cards and charts for any period (7 days to 12 months, or a custom range).
- **Insights:** patterns in the user's own records, with evidence levels and a statistical check against chance.
- **Medical report:** all records for a period, previewed in the app and downloaded as a multi-page PDF in English or Arabic.
- **Interface:** English and Arabic (right to left), light and dark themes, phone and desktop layouts.

## Tech stack

- **Frontend:** React 19, Vite 8, React Router, Tailwind CSS 4, Chart.js.
- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 15 or later, fpdf2 with HarfBuzz for Arabic PDFs.

## Getting started (local development)

These commands are written for Windows PowerShell; on macOS or Linux use `.venv/bin/python` instead.

**You need:** Python 3.13, Node.js 24 (npm 11) and PostgreSQL 15 or later.

### 1. Database
As the `postgres` superuser, create the application role and the two databases (choose your own password):
```sql
CREATE ROLE namat_app LOGIN PASSWORD 'choose-a-password';
CREATE DATABASE namat_dev  OWNER namat_app ENCODING 'UTF8' TEMPLATE template0;
CREATE DATABASE namat_test OWNER namat_app ENCODING 'UTF8' TEMPLATE template0;
```
`namat_test` is used only by the automated tests.

### 2. Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env     # then edit .env: DATABASE_URL and a random JWT_SECRET_KEY
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
The API runs at <http://localhost:8000>, with interactive docs at <http://localhost:8000/docs>.

### 3. Frontend
```powershell
cd frontend
npm install
npm run dev
```
Open <http://localhost:5173>. In development the app calls the API at `http://localhost:8000`; set `VITE_API_BASE_URL` to change that.
## Tests

| What | Command (run from) | Count |
|---|---|---|
| Backend tests | `.venv\Scripts\python.exe -m pytest` (`backend\`) | 206 |
| Migrations match the models | `.venv\Scripts\python.exe -m alembic check` (`backend\`) | — |
| Frontend tests | `npm test` (`frontend\`) | 38 |
| Lint | `npm run lint` (`frontend\`) | — |
| Production build | `npm run build` (`frontend\`) | — |

**Backend test files:**
| File | Tests | Covers |
|---|---|---|
| `test_auth.py` | 28 | registration, login and tokens |
| `test_episodes.py` | 24 | episodes, symptoms and medication |
| `test_daily_logs.py` | 28 | sleep and daily factors |
| `test_analytics.py` | 21 | dashboard analytics |
| `test_insights.py` | 36 | insights |
| `test_reports.py` | 32 | medical report and PDFs |
| `test_security.py` | 37 | headers, caching, every protected route, CORS, error handling and rate limits |

**Frontend test files:** insights, the medical report page, the daily log page and forms, history paging, the API helper, and session expiry.

**Test database:** the backend tests run **only** against a database whose name ends in `_test` (normally `namat_test`, derived from `DATABASE_URL`, or set `TEST_DATABASE_URL`). They create the schema with the real migrations, roll back every test, and use synthetic `example.com` users only.

## Privacy

- Health records stay in Namat's own database and are never sent to outside services.
- Reports and PDFs are generated on request and never stored.
- Responses aren't cached.
- Each user can only ever access their own records.

## Fonts and licences

- **PDF fonts:** Noto Sans and Noto Sans Arabic, under the SIL Open Font License (`backend/app/reports/fonts/OFL.txt`).
- **Interface fonts:** Atkinson Hyperlegible Next, Fraunces and Noto Sans Arabic, all OFL, installed from npm (Fontsource).
- **Arabic interface and PDFs** use the same family, Noto Sans Arabic. Thmanyah isn't used: its licence doesn't allow serving its font files from a public website. `frontend/public/fonts/thmanyah/` stays git-ignored so a local copy can never be committed.
