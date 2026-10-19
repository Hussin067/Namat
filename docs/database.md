# Namat Database

PostgreSQL schema for the Namat migraine tracker: how it is designed, why, and how to run it locally.

**Stack:** PostgreSQL 15+ (developed on 18) · SQLAlchemy 2.x · Alembic · psycopg 3 · pydantic-settings

> All data used in development and tests is **synthetic**. Never load real patient information into a development database or commit it to this repository.

---

## 1. Entity-relationship overview

```mermaid
erDiagram
    users ||--o{ headache_episodes : records
    users ||--o{ medication_doses  : takes
    users ||--o{ sleep_logs        : logs
    users ||--o{ daily_factors     : logs
    headache_episodes ||--o{ episode_symptoms : has
    symptoms          ||--o{ episode_symptoms : "appears in"
    headache_episodes |o--o{ medication_doses : "treated by"
```

| Relationship | Type | On delete |
|---|---|---|
| user → episodes, doses, sleep logs, daily factors | one-to-many | `CASCADE` (deleting a user deletes all their data) |
| episode ↔ symptom (through `episode_symptoms`) | many-to-many | episode deleted → its links deleted; symptom in use → delete **refused** (`RESTRICT`) |
| dose → episode | many-to-one, optional | episode deleted → dose kept, only `episode_id` set to `NULL` |

---

## 2. Tables

Conventions used by every table:

- **Primary keys** are `UUID`, generated in Python (`uuid4`) with a `gen_random_uuid()` server default as a fallback.
- **Timestamps** are `TIMESTAMPTZ` (stored in UTC). User-owned tables have `created_at` / `updated_at`, set by the server.
- **Constraint names** follow a fixed convention (`pk_`, `fk_`, `uq_`, `ck_`, `ix_` + table + columns) so migrations can find them later.
- Optional measurements are `NULL` when not recorded. `NULL` means "unknown", which is different from `0`.

### `users`
| Column | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `email` | VARCHAR(320) | required; **unique ignoring case** (index `uq_users_email_lower` on `lower(email)`) |
| `password_hash` | VARCHAR(255) | required; **only a one-way hash** (Argon2/bcrypt), never the password |
| `display_name` | VARCHAR(100) | optional |
| `timezone` | VARCHAR(64) | default `'UTC'`; IANA name such as `Asia/Riyadh`, decides where the user's "day" starts |
| `is_active` | BOOLEAN | default `true` |
| `created_at`, `updated_at` | TIMESTAMPTZ | server-set |

### `headache_episodes`
One migraine/headache attack.

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id`, `ON DELETE CASCADE` |
| `started_at` | TIMESTAMPTZ | required |
| `ended_at` | TIMESTAMPTZ | `NULL` while ongoing; must be ≥ `started_at` |
| `peak_intensity` | SMALLINT | 0–10 |
| `pain_location` | VARCHAR(30) | one of `left`, `right`, `bilateral`, `frontal`, `occipital`, `behind_eye`, `other` |
| `had_aura` | BOOLEAN | default `false` |
| `notes` | TEXT | optional |

Indexes and constraints: `ix_headache_episodes_user_id_started_at (user_id, started_at DESC)` serves "my episodes, newest first". `UNIQUE (id, user_id)` is the target of the composite foreign key described in section 3.

### `symptoms`
Shared catalog, seeded by the initial migration (13 entries such as *Nausea*, *Sensitivity to light*, *Visual aura*).

| Column | Type | Rules |
|---|---|---|
| `id` | SMALLINT | PK, identity |
| `name` | VARCHAR(60) | unique |
| `category` | VARCHAR(30) | e.g. `digestive`, `sensory`, `aura`, `neurological`, `physical`, `pain` |

### `episode_symptoms`
Link table between episodes and symptoms.

| Column | Type | Rules |
|---|---|---|
| `episode_id` | UUID | PK part; FK → `headache_episodes.id`, `ON DELETE CASCADE` |
| `symptom_id` | SMALLINT | PK part; FK → `symptoms.id`, `ON DELETE RESTRICT`; indexed |
| `severity` | SMALLINT | optional, 1 (mild) – 3 (severe) |

The composite primary key `(episode_id, symptom_id)` stops the same symptom from being recorded twice on one episode. The table has no `user_id`: ownership comes from the episode.

### `medication_doses`
Each dose taken, optionally linked to an episode.

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id`, `ON DELETE CASCADE` |
| `episode_id` | UUID | optional (`NULL` for preventive doses); indexed |
| `medication_name` | VARCHAR(120) | required, free text |
| `dose_amount` | NUMERIC(8,2) | > 0 |
| `dose_unit` | VARCHAR(20) | e.g. `mg`, `ml`, `tablet` |
| `taken_at` | TIMESTAMPTZ | required |
| `relief_rating` | SMALLINT | 0 none · 1 some · 2 good · 3 complete |
| `notes` | TEXT | optional |

Indexes and constraints: `ix_medication_doses_user_id_taken_at (user_id, taken_at DESC)`, plus the composite foreign key `(episode_id, user_id) → headache_episodes(id, user_id) ON DELETE SET NULL (episode_id)`.

### `sleep_logs`
One night of sleep.

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id`, `ON DELETE CASCADE` |
| `sleep_date` | DATE | the date the night started; **unique per user** |
| `bedtime`, `wake_time` | TIMESTAMPTZ | `wake_time > bedtime`, at most 24 hours apart |
| `quality` | SMALLINT | 1 (poor) – 5 (great) |
| `awakenings` | SMALLINT | ≥ 0 |
| `notes` | TEXT | optional |

Sleep duration is **calculated, not stored** (`SleepLog.duration_minutes`), so it can never disagree with the two timestamps.

### `daily_factors`
Possible triggers for one day. Every factor is optional.

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id`, `ON DELETE CASCADE` |
| `log_date` | DATE | **unique per user** |
| `stress_level` | SMALLINT | 0–10 |
| `caffeine_mg` | INTEGER | ≥ 0 |
| `water_ml` | INTEGER | ≥ 0 |
| `alcohol_units` | NUMERIC(4,1) | ≥ 0 |
| `exercise_minutes` | SMALLINT | 0–1440 |
| `skipped_meal`, `menstruating` | BOOLEAN | optional |
| `notes` | TEXT | optional |

---

## 3. User data isolation

The schema is prepared for authenticated, per-user access:

1. **Every user-owned table has a required `user_id`.** API code (added in the auth task) must always filter by the logged-in user, e.g. `select(HeadacheEpisode).where(HeadacheEpisode.user_id == current_user.id)`. The database cannot know who is logged in, so this filter is the application's job.
2. **Cross-user links are impossible at the database level.** A plain FK on `medication_doses.episode_id` would let a dose owned by user B point at user A's episode. Instead, the FK is on `(episode_id, user_id)` → `headache_episodes(id, user_id)`, so PostgreSQL rejects any dose whose episode belongs to someone else.
   - `ON DELETE SET NULL (episode_id)` (PostgreSQL 15+) clears only the episode link when an episode is deleted. A plain `SET NULL` would also clear `user_id` and fail.
3. **UUIDs instead of sequential IDs** mean record IDs can't be guessed by counting. This is *not* a substitute for the ownership filter in point 1.
4. **Account deletion** is a single `DELETE FROM users`; `ON DELETE CASCADE` removes everything the user owns.
5. **Passwords:** only `password_hash` exists. `User.__repr__` leaves it out so it never appears in logs.

Possible later hardening (not part of this task): PostgreSQL row-level security (RLS) as a second line of defence.

---

## 4. Code layout

```
backend/
├── .env                  # local secrets (git-ignored, never commit)
├── .env.example          # template with placeholder values (committed)
├── alembic.ini           # Alembic settings; deliberately contains no URL
├── alembic/
│   ├── env.py            # loads DATABASE_URL from .env and Base.metadata
│   └── versions/         # migration files, oldest → newest
├── app/
│   ├── core/config.py    # Settings (pydantic-settings); DATABASE_URL as SecretStr
│   ├── db/base.py        # DeclarativeBase, naming convention, uuid_pk, TimestampMixin
│   ├── db/session.py     # engine, SessionLocal, get_db() FastAPI dependency
│   └── models/           # user, episode (+ symptom, link), medication, sleep, daily_factor
└── scripts/
    ├── seed_sample_data.py   # inserts and reads back synthetic data
    └── verify_database.py    # checks constraints & isolation, then rolls back
```

---

## 5. Local development setup (Windows, PowerShell)

Everything here is free and local: no paid hosting is required.

### 5.1 Install PostgreSQL
Install PostgreSQL 15 or newer from <https://www.postgresql.org/download/windows/> (the EDB installer). Remember the password you set for the `postgres` superuser. Check that it is running:

```powershell
Get-Service postgresql*
& "C:\Program Files\PostgreSQL\18\bin\pg_isready.exe" -h localhost -p 5432
```

### 5.2 Create a dedicated role and database
The app never connects as the `postgres` superuser.

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost
```

At the `postgres=#` prompt:

```sql
CREATE ROLE namat_app WITH LOGIN;
\password namat_app
CREATE DATABASE namat_dev OWNER namat_app ENCODING 'UTF8' TEMPLATE template0;
REVOKE CONNECT ON DATABASE namat_dev FROM PUBLIC;
\q
```

`\password` asks for the password interactively, so it does not end up in your shell history.

### 5.3 Configure `backend/.env`
```powershell
Copy-Item backend\.env.example backend\.env
code backend\.env
```

Set the real password in place of `CHANGE_ME`:

```
DATABASE_URL=postgresql+psycopg://namat_app:YOUR_PASSWORD@localhost:5432/namat_dev
```

If the password contains `@ : / # % ?`, URL-encode those characters (e.g. `@` → `%40`), or choose a letters-and-digits password.

Check that it is ignored by git (this should print a matching `.gitignore` rule):

```powershell
git check-ignore -v backend/.env
```

### 5.4 Install Python dependencies
```powershell
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 5.5 Create the tables
```powershell
alembic upgrade head
alembic current          # should print: cb06b672a76b (head)
```

### 5.6 Load and verify synthetic data
```powershell
python -m scripts.seed_sample_data   # two sample users, 14 days of data, printed back
python -m scripts.verify_database    # expect: 12/12 checks passed
```

The seed script only runs when `APP_ENV=development`, and it is safe to re-run (previous sample users are deleted first).

### 5.7 Make sure the API still runs
```powershell
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/health> and expect `{"status": "healthy"}`.

---

## 6. Migration workflow

| Task | Command (from `backend/`, venv active) |
|---|---|
| Apply all pending migrations | `alembic upgrade head` |
| Show current revision | `alembic current` |
| Show history | `alembic history --verbose` |
| Undo the last migration | `alembic downgrade -1` |
| Generate a migration after editing models | `alembic revision --autogenerate -m "short description"` |
| Check models and database are in sync | `alembic check` |
| Preview SQL without running it | `alembic upgrade head --sql` |

Rules of thumb:

- **Always read an autogenerated migration before running it.** Autogenerate can miss renames (it sees them as drop + add, which loses data) and some server defaults.
- New models must be imported in `app/models/__init__.py`, or autogenerate will not see them.
- Never edit a migration that has already been applied somewhere shared. Write a new one instead.
- Test both directions locally: `alembic downgrade -1` then `alembic upgrade head`.

---

## 7. Security checklist

- [x] `.env` and every `.env.*` except `.env.example` are git-ignored.
- [x] `alembic.ini` contains no database URL; the URL comes only from `.env` or the environment.
- [x] `DATABASE_URL` is a `SecretStr`, so printing the settings shows `**********`.
- [x] The app uses a non-superuser role (`namat_app`) that owns only `namat_dev`.
- [x] Only password hashes are stored, and they are excluded from `repr()`.
- [x] Sample data uses reserved `example.com` addresses and a placeholder that can never match a password.
- [ ] Later (auth task): hash passwords with Argon2/bcrypt, and enforce the `user_id` filter on every query.
- [ ] Later (deployment): use TLS (`?sslmode=require`) and store the hosted database URL in the host's secret settings.

---

## 8. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `password authentication failed for user "namat_app"` | `backend/.env` still has `CHANGE_ME`, has a typo, or wasn't saved. A password with special characters must be URL-encoded. |
| `password authentication failed for user "postgres"` | Wrong superuser password. psql shows nothing while you type; check Caps Lock and the keyboard language. To reset it, temporarily set `trust` for localhost in `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`, restart the service, run `\password postgres`, then **restore `scram-sha-256` and restart again**. |
| `connection refused` | The service is stopped: `Start-Service postgresql-x64-18` (as Administrator). |
| `ValidationError ... database_url Field required` | `backend/.env` is missing, or has no `DATABASE_URL` line. |
| `ModuleNotFoundError: No module named 'app'` | Run commands from `backend/`, and run scripts with `python -m scripts.<name>`. |
| psql warning `Console code page (437) differs from Windows code page` | Harmless for this project. Run `chcp 1252` before psql to silence it. |
