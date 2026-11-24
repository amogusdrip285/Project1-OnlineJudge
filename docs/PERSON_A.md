# Person A — Backend & Database: Detailed Plan

You own `backend/`, the database schema/migrations, the REST API, seed data, and the repo
skeleton (`docker-compose.yml`, `.env.example`, CI). B (judge) and C (frontend) both depend on you,
so **your first priority is always to unblock them**: tables for B, real endpoints for C.

Specs you implement: [MASTER_PLAN.md](MASTER_PLAN.md) §3 (config), §4 (DB), §5 (testcase files),
§6 (API). Features: [FEATURES.md](FEATURES.md) (F1, F3, F5–F8, F12, F13 + small parts of others).

---

## 1. Tech choices (backend)

| Concern | Choice | Notes |
|---|---|---|
| Framework | FastAPI | Sync endpoints (`def`, not `async def`) — simpler, runs in a threadpool |
| DB access | SQLAlchemy 2.0 (sync) + `psycopg` 3 | `DATABASE_URL` `postgresql://` is rewritten to `postgresql+psycopg://` |
| Migrations | Alembic | Runs `alembic upgrade head` on container start |
| Config | `pydantic-settings` | All settings from env vars (§3.2) |
| Passwords | `bcrypt` | Never store or log plain passwords |
| Tokens | `PyJWT`, HS256 | Payload: `{"sub": user_id, "role": ..., "exp": ...}` |
| Uploads | `python-multipart` | Zip testcases, CSV import, checker upload |
| Deps | `uv` + `uv.lock` | `uv sync`, `uv run pytest` |
| Lint/format | `ruff` | `uv run ruff check . && uv run ruff format .` |
| Tests | `pytest` + FastAPI `TestClient` | DB tests use a real Postgres (compose `db` or CI service) |

---

## 2. Code layout

```
backend/
├── Dockerfile
├── entrypoint.sh              # alembic upgrade head → uvicorn
├── pyproject.toml / uv.lock
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 0001_initial_schema.py      # MVP schema (MASTER_PLAN §4.2)
│       └── f01_..., f02_...            # one migration per feature (FEATURES §3)
├── app/
│   ├── main.py                # create_app(): routers, CORS, error handlers
│   ├── config.py              # Settings (env vars)
│   ├── db.py                  # engine, SessionLocal, get_db()
│   ├── errors.py              # AppError + handlers → {"error": {code, message}}
│   ├── security.py            # hash/verify password, create/decode JWT
│   ├── deps.py                # get_current_user, require_admin
│   ├── pagination.py          # Page params + envelope helper
│   ├── models/                # SQLAlchemy models (1 file per area)
│   ├── schemas/               # Pydantic request/response models (match §6.2 exactly)
│   ├── routers/               # health, auth, contests, problems, submissions, admin/*
│   └── services/              # business logic: scoring, testcase_storage, submissions, ...
├── scripts/
│   ├── seed.py                # demo users, contest, problems, testcases
│   └── fake_judge.py          # marks PENDING → AC (for C and demos before the judge is ready)
└── tests/
```

**Rule:** routers stay thin (parse → call service → return schema). SQL and rules live in
`services/`, so they can be unit tested.

---

## 3. Week-by-week

### Week 1 — Skeleton, schema, auth (unblock B and C)

| Day | Task | Done when |
|---|---|---|
| Day 0 | Repo skeleton: folders, `docker-compose.yml`, `.env.example`, `.gitignore`, `.gitattributes`, CI, PR template; backend app with `/api/health`, error envelope, config, Alembic | `docker compose up --build` → `GET localhost:8000/api/health` → `{"status":"ok"}`. Pushed to `main`. |
| Day 0 | `0001_initial_schema` migration + models for all MVP tables | B can `docker compose up db backend` and see tables in Postgres |
| 1 | **Tell B and C the skeleton is on `main`** | They branch from it |
| 1–2 | `security.py` + `POST /api/auth/login`, `GET /api/auth/me`, `deps.py` | Tests: correct login, wrong password → 401, expired token → 401, admin guard → 403 |
| 2–3 | `scripts/seed.py`: 1 admin, 3 students, 1 contest `project120261`, 5 "Week 1" problems with testcases in `data/seed/problems/` | `docker compose exec backend uv run python -m scripts.seed` is idempotent (safe to run twice) |
| 3–4 | `pagination.py`; `GET /api/contests`, `GET /api/contests/{id}` | Matches §6.2 JSON field by field |
| 5 | `scripts/fake_judge.py` | C can see submissions go PENDING → AC without B's judge |

### Week 2 — Core student endpoints (walking skeleton)

Day-by-day version with exact rules, seed data and tests: [WEEK2_PLAN.md §2](WEEK2_PLAN.md).
Week-1 carry-over (login, seed, contests endpoints, `fake_judge.py`) is done first.

| Task | Notes |
|---|---|
| `services/scoring.py` | Best score per (user, contest, problem): `MAX(score)`. One SQL query with `GROUP BY`, not a loop (avoid N+1). |
| `GET /api/contests/{id}/problems` | Search (`ILIKE` on title/code), pagination, `points_earned`, `is_complete`, `total_points_earned`, `total_max_points` (over **all** problems) |
| `GET /api/contests/{id}/problems/{pid}` | Includes sample tests read from files (`is_sample=true`) |
| `POST .../submit` | Validate language, `MAX_SOURCE_BYTES` → 413, cooldown → 429 (check last submission time in DB, no Redis needed), snapshot `max_points`, insert `PENDING` |
| `GET /api/contests/{id}/submissions`, `GET /api/submissions/{id}` | Owner or admin; others get **404** |
| Smoke test script `scripts/smoke_test.py` (with B, C) | Login → submit A+B → poll → AC. Runs in CI. |

**Milestone M2 (end of week 2):** real end-to-end on `main` with B's judge and C's UI.

### Week 3 — Admin + hardening (MVP complete)

| Task | Notes |
|---|---|
| `POST /api/admin/contests`, `POST /api/admin/problems`, `POST /api/admin/contests/{id}/problems` | 409 on duplicate `code` |
| `POST /api/admin/problems/{pid}/testcases` (zip) | `services/testcase_storage.py` — see §4 security rules |
| Error handling pass | Every error uses the envelope; no stack traces in responses; log server-side |
| Tests to ≥ 80% coverage | `uv run pytest --cov=app` |

### Week 4 — P1 features (FEATURES.md)

Order: **F3** (contest status — changes the contest object) → **F2 endpoints** (B and C need
them) → **F1** leaderboard → **F6** import + private contests → **F5** CSV export → **F7** rejudge → **F8** stats.
Each feature: migration `fNN_*` + service + router + tests, in its own PR.

### Week 5 — P2 features

**F12** profile stats, **F13** announcements, then the small backend parts of **F9** (checker
fields + upload), **F10** (`sample` block in submission detail), **F11** (job endpoints).
Feature freeze Friday.

### Week 6 — Hardening & demo

Demo seed data (a realistic class: 30 students, 10 problems, some submissions), bug fixes from
the integration session, README, help run the final checklists.

---

## 4. Security checklist (your responsibility)

- [ ] Passwords hashed with bcrypt; login error says "Invalid username or password" (doesn't reveal which)
- [ ] `JWT_SECRET` from env; backend refuses to start if it is still `change-me...` and `ENV=production`
- [ ] Every query uses SQLAlchemy parameters — never build SQL with f-strings
- [ ] Students only see their own submissions/source code (404 otherwise)
- [ ] All `/api/admin/*` routes use `require_admin`
- [ ] Zip upload: reject entries with `/`, `\`, `..`, absolute paths, or names not matching `^\d+\.(in|out)$`; cap total unzipped size (e.g. 50 MB) to stop zip bombs; normalize CRLF → LF
- [ ] CSV import: cap file size and rows; validate every row before saving
- [ ] Source size cap + submit/run cooldowns
- [ ] CORS only allows `CORS_ORIGINS`
- [ ] Error responses never include stack traces or SQL

---

## 5. Testing plan

| Layer | What | How |
|---|---|---|
| Unit | `security.py`, `scoring.py` math, zip validation, CSV parsing | Plain pytest, no DB |
| API | Every endpoint: success, 401, 403, 404, validation errors | `TestClient` + real Postgres test DB, each test in a rolled-back transaction |
| Migration | `alembic upgrade head` works on an empty DB and models match the migrations | `tests/test_migrations.py` (skipped when no DB is available) |
| Integration | Full flow with the judge | `scripts/smoke_test.py` in CI |

Run locally: `docker compose up -d db` then `cd backend && uv run pytest`.

---

## 6. Helping B and C

- **B** needs: the tables (Day 0), seed problems with testcases on disk (week 1), and the
  column-ownership rules (MASTER_PLAN §4.3). Tell B whenever a migration touches `submissions`,
  `test_runs` or `plagiarism_*`.
- **C** needs: the JSON in MASTER_PLAN §6.2 to stay accurate. When an endpoint is done, post in the
  group chat: "`GET /api/...` is live on main". C can then turn off that mock.
- Swagger UI at `http://localhost:8000/docs` is the quickest way for both to try your endpoints.

---

## 7. Definition of done (per PR)

- [ ] Endpoint matches MASTER_PLAN / FEATURES JSON exactly (field names, types, status codes)
- [ ] Tests for success + main error cases, all passing
- [ ] `uv run ruff check .` clean
- [ ] Migration included if the schema changed, and it runs on an empty DB
- [ ] Docs updated if a table/field changed; team told in the group chat
- [ ] `docker compose up --build` still works
