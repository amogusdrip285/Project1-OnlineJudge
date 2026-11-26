# Online Judge — Master Integration Plan

This document is the **single source of truth** for how the three parts (Backend, Judge,
Frontend) fit together. If your code follows this file, merging is just `git merge`.

- Scope, MVP tasks per person: see [PLAN.md](PLAN.md).
- Features for weeks 4–6 and their DB/API specs: see [FEATURES.md](FEATURES.md).
- Week 2 day-by-day plan for A, B, C: see [WEEK2_PLAN.md](WEEK2_PLAN.md).
- This file: the **shared specs** (DB, API, judge), **conventions**, **git workflow** and **schedule**.

> If you need to change something in this file (a table, a JSON field…), just change it and tell
> the others in the group chat so the docs and the code stay the same.

---

## 0. Roles

| Tag | Person | Owns folder | Owns spec |
|---|---|---|---|
| **A** | Backend | `backend/` | DB schema + migrations, REST API implementation |
| **B** | Judge | `judge/` | Judge behavior, verdict rules, language configs |
| **C** | Frontend | `frontend/` | UI, API client, mocks |
| **All** | — | root files, `docs/` | Everything in this document |

---

## 1. Golden rules for seamless merging

1. **Stay in your own folder.** A only edits `backend/`, B only edits `judge/`, C only edits `frontend/`.
   Need a change in someone else's folder? Message the owner first so you don't both edit the same file.
2. **Announce changes to shared files** in the group chat: `docker-compose.yml`, `.env.example`,
   `.gitignore`, `docs/**`, `.github/**`, `data/seed/**`.
3. **Code to the spec.** Use the table names (§4), JSON field names (§6) and judge rules (§7)
   exactly as written, so the parts fit together without changes.
4. **`main` always runs.** `docker compose up --build` on `main` must start everything without errors.
5. **Small PRs, merged often.** Aim for at least one merged PR per person every 2–3 days. A
   branch that lives longer than a week is a merge conflict waiting to happen.
6. **Build against mocks, not against each other.** Nobody waits for a teammate (see §9).

---

## 2. Repository layout (fixed)

```
Project1-OnlineJudge/
├── .github/
│   ├── pull_request_template.md
│   └── workflows/ci.yml
├── .env.example                 # shared — every env var used by any service
├── .gitignore                   # shared
├── docker-compose.yml           # shared
├── README.md                    # shared — how to run
├── docs/
│   ├── PLAN.md
│   ├── MASTER_PLAN.md           # this file
│   ├── FEATURES.md              # weeks 4–6 features + their DB/API specs
│   ├── WEEK2_PLAN.md            # week 2 (M2) day-by-day plan
│   └── reports/                 # weekly progress reports for the teacher
├── data/
│   ├── seed/problems/           # committed sample problems (testcases for seed data)
│   └── problems/                # placeholder only; runtime testcases live in the `problems` volume (§3.3)
├── scripts/
│   └── smoke_test.py            # end-to-end check used by CI (§10.4)
├── backend/                     # A
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/                 # ONLY A creates migrations
│   ├── app/
│   └── tests/
├── judge/                       # B
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── languages.yaml
│   ├── judge/
│   ├── samples/                 # programs that must produce each verdict
│   └── tests/
└── frontend/                    # C
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── api/                 # API client + types matching §6
        └── mocks/               # mock responses matching §6 exactly
```

---

## 3. Runtime configuration (fixed)

### 3.1 Services, ports, hostnames

| Compose service | Port (host:container) | Talks to | Notes |
|---|---|---|---|
| `db` | `5432:5432` | — | `postgres:16` |
| `backend` | `8000:8000` | `db` | Base path `/api`, Swagger at `/docs` |
| `judge` | none | `db` | **No network except to `db`** |
| `frontend` | `5173:5173` | `backend` (from browser) | Vite dev server |

Inside Docker, services reach each other by service name (`db`, `backend`), **never** `localhost`.

### 3.2 Environment variables (`.env.example`)

```dotenv
# --- Database (backend + judge) ---
POSTGRES_USER=oj
POSTGRES_PASSWORD=change-me
POSTGRES_DB=oj
DATABASE_URL=postgresql://oj:change-me@db:5432/oj

# --- Backend ---
SEED_ON_START=true               # dev: load demo users/contest/problems on start (idempotent)
SEED_DIR=/data/seed/problems     # ./data/seed is mounted read-only into the backend
JWT_SECRET=change-me-to-a-long-random-string
JWT_EXPIRE_MINUTES=720
CORS_ORIGINS=http://localhost:5173
PROBLEMS_DIR=/data/problems
MAX_SOURCE_BYTES=65536
SUBMIT_COOLDOWN_SECONDS=5

# --- Judge ---
PROBLEMS_DIR=/data/problems
JUDGE_POLL_INTERVAL_MS=500
JUDGE_STALE_AFTER_SECONDS=120
JUDGE_COMPILE_TIMEOUT_SECONDS=10
JUDGE_MAX_OUTPUT_BYTES=16777216

# --- Frontend ---
VITE_API_BASE_URL=http://localhost:8000/api
VITE_USE_MOCKS=false
```

Rules: adding a variable means adding it to `.env.example` in the same PR. Never commit `.env`.

### 3.3 Shared volume

The named volume `problems` is mounted at **`/data/problems`** in `backend` (read-write) and
`judge` (**read-only**). It is a named volume, not a bind mount of `./data/problems`, because the
backend runs as uid 10001 and cannot write into a host folder owned by another uid on Linux/CI.
Inspect it with `docker compose exec backend ls /data/problems`; wipe it with `docker compose down -v`.
The backend also mounts `./data/seed` read-only at `/data/seed` for the seed script.

### 3.4 docker-compose skeleton (created on Day 0)

```yaml
services:
  db:
    image: postgres:16
    env_file: .env
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
      interval: 3s
      retries: 20

  backend:
    build: ./backend
    env_file: .env
    ports: ["8000:8000"]
    volumes: ["problems:/data/problems"]
    depends_on: { db: { condition: service_healthy } }

  judge:
    build: ./judge
    env_file: .env
    volumes: ["problems:/data/problems:ro"]
    depends_on: { backend: { condition: service_started } }   # backend runs migrations
    networks: [internal]
    # resource caps for the whole worker; per-run limits are set inside the judge
    mem_limit: 1g
    pids_limit: 256

  frontend:
    build: ./frontend
    env_file: .env
    ports: ["5173:5173"]

volumes:
  pgdata:
  problems:

networks:
  internal:
    internal: true   # judge cannot reach the internet
```

(`db` must also join `internal` plus the default network; A finalizes this on Day 0.)

**Who runs migrations:** the `backend` container runs `alembic upgrade head` on startup, then the
seed script if `SEED_ON_START=true`. The judge
**never** creates or alters tables. If the judge starts before the tables exist, it retries.

---

## 4. Database spec

Owned by **A**. Only A writes Alembic migrations. B reads/writes the columns listed in §4.3.

### 4.1 Conventions

- Table names: plural `snake_case`. Columns: `snake_case`.
- Primary keys: `id BIGSERIAL`.
- Timestamps: `TIMESTAMPTZ`, stored in **UTC**.
- Enums stored as `TEXT` with a `CHECK` constraint (easier to change than Postgres enums).

### 4.2 Schema

```sql
CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name     TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('student','admin')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE contests (
  id          BIGSERIAL PRIMARY KEY,
  code        TEXT UNIQUE NOT NULL,          -- e.g. 'project120261'
  title       TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  start_time  TIMESTAMPTZ,
  end_time    TIMESTAMPTZ,
  is_public   BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE problems (
  id              BIGSERIAL PRIMARY KEY,
  code            TEXT UNIQUE NOT NULL,      -- e.g. 'P_ADD_SUB_MUL_DIV'
  title           TEXT NOT NULL,
  statement_md    TEXT NOT NULL,
  level           TEXT NOT NULL CHECK (level IN ('easy','medium','hard')),
  time_limit_ms   INT  NOT NULL DEFAULT 1000,
  memory_limit_mb INT  NOT NULL DEFAULT 256,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE contest_problems (
  contest_id  BIGINT NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
  problem_id  BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
  max_points  INT    NOT NULL CHECK (max_points > 0),
  order_index INT    NOT NULL,
  PRIMARY KEY (contest_id, problem_id)
);

CREATE TABLE testcases (
  id          BIGSERIAL PRIMARY KEY,
  problem_id  BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
  order_index INT    NOT NULL,               -- 1, 2, 3, ...
  input_path  TEXT   NOT NULL,               -- relative to PROBLEMS_DIR
  output_path TEXT   NOT NULL,               -- relative to PROBLEMS_DIR
  is_sample   BOOLEAN NOT NULL DEFAULT false,
  UNIQUE (problem_id, order_index)
);

CREATE TABLE submissions (
  id             BIGSERIAL PRIMARY KEY,
  user_id        BIGINT NOT NULL REFERENCES users(id),
  contest_id     BIGINT NOT NULL REFERENCES contests(id),
  problem_id     BIGINT NOT NULL REFERENCES problems(id),
  language       TEXT   NOT NULL CHECK (language IN ('cpp17','python3')),
  source_code    TEXT   NOT NULL,
  max_points     INT    NOT NULL,            -- snapshot at submit time
  status         TEXT   NOT NULL DEFAULT 'PENDING'
                 CHECK (status IN ('PENDING','JUDGING','AC','WA','TLE','MLE','RE','CE','PARTIAL','SE')),
  score          INT    NOT NULL DEFAULT 0,
  tests_passed   INT    NOT NULL DEFAULT 0,
  tests_total    INT    NOT NULL DEFAULT 0,
  time_ms        INT,                        -- max over tests
  memory_kb      INT,                        -- max over tests
  compile_output TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  judging_started_at TIMESTAMPTZ,
  judged_at      TIMESTAMPTZ
);
CREATE INDEX ix_submissions_pending ON submissions (id) WHERE status = 'PENDING';
CREATE INDEX ix_submissions_user_contest_problem ON submissions (user_id, contest_id, problem_id);

CREATE TABLE submission_results (
  submission_id BIGINT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  testcase_id   BIGINT NOT NULL REFERENCES testcases(id) ON DELETE CASCADE,
  verdict       TEXT   NOT NULL CHECK (verdict IN ('AC','WA','TLE','MLE','RE')),
  time_ms       INT    NOT NULL,
  memory_kb     INT    NOT NULL,
  PRIMARY KEY (submission_id, testcase_id)
);
```

### 4.3 Column ownership (who writes what)

| Table / column | Written by | Read by |
|---|---|---|
| `users`, `contests`, `problems`, `contest_problems`, `testcases` | **A** only | A, B (read-only) |
| `submissions` — insert row (`user_id`…`max_points`, `status='PENDING'`) | **A** | — |
| `submissions.status` PENDING → JUDGING, `judging_started_at` | **B** | A |
| `submissions.status` JUDGING → final, `score`, `tests_passed`, `tests_total`, `time_ms`, `memory_kb`, `compile_output`, `judged_at` | **B** | A |
| `submission_results` | **B** only | A |

A must never change a submission's status after inserting it (only exception: rejudge, FEATURES.md F7). B must never insert submissions or
touch other tables. Following this means the two can't overwrite each other's data.

---

## 5. Testcase files

```
/data/problems/<problem_id>/tests/1.in
/data/problems/<problem_id>/tests/1.out
/data/problems/<problem_id>/tests/2.in
...
```

- Numbering starts at **1**, no gaps. `testcases.order_index` = the number.
- `testcases.input_path` = `"<problem_id>/tests/<n>.in"` (relative to `PROBLEMS_DIR`).
- **A normalizes line endings to `\n` (LF) on upload.** Windows editors save CRLF and that
  causes false WA verdicts.
- Upload format: a `.zip` holding `1.in, 1.out, 2.in, 2.out, …` at the root. A rejects the zip
  if any pair is missing, a name doesn't match `^\d+\.(in|out)$`, or a path contains `/`, `\`, or `..`.
- Replacing testcases = delete the problem's folder + rows, then write the new ones, all in one transaction.
- Seed problems live in `data/seed/problems/<problem_code>/` in git (`problem.yaml`,
  `statement.md`, `tests/`, `solutions/`); A's seed script copies the tests into
  `PROBLEMS_DIR/<problem_id>/tests/`. Format: [WEEK2_PLAN.md §2.3](WEEK2_PLAN.md).

---

## 6. REST API spec

Owned by **A** (implementation) and **C** (consumer). C's `src/api/types.ts` and A's response
models must match this section **field for field**.

### 6.1 General conventions

| Item | Rule |
|---|---|
| Base URL | `/api` |
| Format | JSON, `Content-Type: application/json` (except zip upload: `multipart/form-data`, field `file`) |
| Field names | `snake_case` everywhere (frontend uses the same names, no camelCase conversion) |
| IDs | integers |
| Timestamps | ISO 8601 UTC strings, e.g. `"2026-11-20T09:49:00Z"` |
| Auth | `Authorization: Bearer <token>` on every endpoint except `/auth/login` |
| Pagination | query `page` (starts at **1**), `size` (default 5, max 100) |
| Enum values | `level`: `easy/medium/hard`; `language`: `cpp17/python3`; `status`: as in §7.2 |

**Paginated response envelope**

```json
{ "items": [ ... ], "page": 1, "size": 5, "total": 53 }
```

**Error envelope** (every non-2xx response)

```json
{ "error": { "code": "NOT_FOUND", "message": "Problem not found" } }
```

| HTTP | `error.code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Bad input (message says which field) |
| 401 | `UNAUTHORIZED` | Missing/expired token → frontend redirects to login |
| 403 | `FORBIDDEN` | Logged in but not allowed |
| 404 | `NOT_FOUND` | — |
| 409 | `CONFLICT` | Duplicate username/code |
| 413 | `SOURCE_TOO_LARGE` | Source > `MAX_SOURCE_BYTES` |
| 429 | `RATE_LIMITED` | Submitted again within `SUBMIT_COOLDOWN_SECONDS` |
| 500 | `INTERNAL_ERROR` | Never leak stack traces |

### 6.2 Endpoints with exact shapes

#### `POST /api/auth/login`
```json
// request
{ "username": "student1", "password": "123456" }
// 200
{
  "token": "eyJhbGciOi...",
  "user": { "id": 2, "username": "student1", "full_name": "Nguyen Van A", "role": "student" }
}
```

#### `GET /api/auth/me`
```json
{ "id": 2, "username": "student1", "full_name": "Nguyen Van A", "role": "student" }
```

#### `GET /api/contests?page=1&size=5`
```json
{
  "items": [
    {
      "id": 1, "code": "project120261", "title": "Project 1 - 2026.1",
      "start_time": "2026-09-01T00:00:00Z", "end_time": "2027-01-15T00:00:00Z",
      "problem_count": 53
    }
  ],
  "page": 1, "size": 5, "total": 1
}
```

#### `GET /api/contests/{contest_id}`
```json
{
  "id": 1, "code": "project120261", "title": "Project 1 - 2026.1",
  "description": "Weekly exercises", "start_time": "2026-09-01T00:00:00Z",
  "end_time": "2027-01-15T00:00:00Z"
}
```

#### `GET /api/contests/{contest_id}/problems?search=&page=1&size=5`
`search` matches title or code, case-insensitive. Sorted by `order_index`. Totals are over
**all** problems of the contest, not just the current page.
```json
{
  "items": [
    {
      "id": 11, "code": "P_ADD_SUB_MUL_DIV",
      "title": "Week 1 - Add Subtract Multiplication Division of A and B",
      "level": "easy", "max_points": 100, "points_earned": 100, "is_complete": true
    },
    {
      "id": 15, "code": "P_HHMMSS_TO_SECONDS",
      "title": "Week 1 - Convert hh:mm:ss to seconds",
      "level": "easy", "max_points": 140, "points_earned": 0, "is_complete": false
    }
  ],
  "page": 1, "size": 5, "total": 53,
  "total_points_earned": 5170,
  "total_max_points": 5170
}
```
`points_earned` = `MAX(score)` over the user's submissions for that problem in that contest
(0 if none). `is_complete` = `points_earned == max_points`.

#### `GET /api/contests/{contest_id}/problems/{problem_id}`
```json
{
  "id": 11, "code": "P_ADD_SUB_MUL_DIV",
  "title": "Week 1 - Add Subtract Multiplication Division of A and B",
  "statement_md": "Given two integers **a** and **b** ...",
  "level": "easy", "time_limit_ms": 1000, "memory_limit_mb": 256,
  "max_points": 100, "points_earned": 100,
  "samples": [ { "input": "3 5\n", "output": "8\n-2\n15\n0\n" } ],
  "languages": ["cpp17", "python3"]
}
```

#### `POST /api/contests/{contest_id}/problems/{problem_id}/submit`
```json
// request
{ "language": "cpp17", "source_code": "#include <bits/stdc++.h>\n..." }
// 201
{ "submission_id": 1234, "status": "PENDING" }
```

#### `GET /api/contests/{contest_id}/submissions?problem_id=&page=1&size=10`
Current user's submissions, newest first. Admins can add `user_id=`.
```json
{
  "items": [
    {
      "id": 1234, "problem_id": 11, "problem_title": "Week 1 - Add Subtract ...",
      "language": "cpp17", "status": "AC", "score": 100, "max_points": 100,
      "tests_passed": 10, "tests_total": 10, "time_ms": 12, "memory_kb": 3420,
      "created_at": "2026-11-20T09:40:00Z"
    }
  ],
  "page": 1, "size": 10, "total": 37
}
```

#### `GET /api/submissions/{submission_id}`
Owner or admin only (others get 404, so they can't learn that it exists).
```json
{
  "id": 1234, "contest_id": 1, "problem_id": 11, "problem_title": "Week 1 - Add Subtract ...",
  "language": "cpp17", "source_code": "#include ...",
  "status": "PARTIAL", "score": 70, "max_points": 100,
  "tests_passed": 7, "tests_total": 10, "time_ms": 1000, "memory_kb": 3420,
  "compile_output": null,
  "created_at": "2026-11-20T09:40:00Z", "judged_at": "2026-11-20T09:40:03Z",
  "results": [
    { "order_index": 1, "verdict": "AC",  "time_ms": 3,    "memory_kb": 3300 },
    { "order_index": 8, "verdict": "TLE", "time_ms": 1000, "memory_kb": 3420 }
  ]
}
```
While `PENDING`/`JUDGING`: `score` 0, `results` `[]`, `judged_at` `null`.

#### Admin endpoints (role `admin`, otherwise 403)

| Method & path | Request | Response |
|---|---|---|
| `POST /api/admin/contests` | `{code, title, description, start_time, end_time, is_public}` | 201 contest object |
| `POST /api/admin/problems` | `{code, title, statement_md, level, time_limit_ms, memory_limit_mb}` | 201 problem object |
| `POST /api/admin/problems/{id}/testcases` | multipart `file` (zip), optional form field `sample_count` (first N are samples) | 201 `{ "testcase_count": 10 }` |
| `POST /api/admin/contests/{id}/problems` | `{problem_id, max_points, order_index}` | 201 `{contest_id, problem_id, max_points, order_index}` |

### 6.3 Keeping both sides in sync

- FastAPI generates `http://localhost:8000/openapi.json`. Once A's endpoints exist, C
  generates TypeScript types from it (`npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts`)
  and CI checks the generated file is up to date (§10).
- Until then, C writes `src/api/types.ts` by hand from §6.2, and A's Pydantic models are written
  from the same section.

---

## 7. Judge rules

Owned by **B**. A and C depend only on the **results** written to the DB.

### 7.1 Job claiming (exact SQL)

```sql
UPDATE submissions
SET status = 'JUDGING', judging_started_at = now()
WHERE id = (
  SELECT id FROM submissions
  WHERE status = 'PENDING'
  ORDER BY id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
RETURNING id, problem_id, language, source_code, max_points;
```

- Poll every `JUDGE_POLL_INTERVAL_MS` when the queue is empty.
- **Stuck job recovery:** at startup and every minute, the judge resets jobs that have been
  `JUDGING` longer than `JUDGE_STALE_AFTER_SECONDS` back to `PENDING` (handles a crashed worker).
- All results for a submission (`submission_results` rows + the `submissions` update) are written
  in **one transaction**.

### 7.2 Verdict and score rules

Per test: `AC`, `WA`, `TLE`, `MLE`, `RE`.

Final `status`:
1. Compile failed → `CE`, `score = 0`, `compile_output` = compiler stderr (cut to 10 KB).
2. Problem has 0 testcases or the judge crashes → `SE`, `score = 0`.
3. All tests `AC` → `AC`.
4. ≥ 1 test `AC` → `PARTIAL`.
5. Otherwise → the verdict of the **first** failed test (`WA`/`TLE`/`MLE`/`RE`).

`score = floor(max_points * tests_passed / tests_total)` (an integer).
`time_ms`, `memory_kb` = maximum over all tests that were run.

**Every test is always run** (no stopping at the first failure), because the score is partial.

### 7.3 Output comparison

Compare after: converting `\r\n` → `\n`, removing trailing spaces/tabs on each line, and removing
trailing empty lines. Everything else must match exactly.

### 7.4 Languages (`judge/languages.yaml`)

```yaml
cpp17:
  source_file: main.cpp
  compile: ["g++", "-O2", "-std=c++17", "-pipe", "-o", "main", "main.cpp"]
  run: ["./main"]
python3:
  source_file: main.py
  compile: null
  run: ["python3", "main.py"]
```

To add a language: B adds it here **and** A adds it to the `CHECK` constraint + the API
`languages` list.

---

## 8. Code conventions (per folder)

| | Backend (A) | Judge (B) | Frontend (C) |
|---|---|---|---|
| Language | Python 3.12 | Python 3.12 | TypeScript (strict) |
| Format | `ruff format` | `ruff format` | `prettier` |
| Lint | `ruff check` | `ruff check` | `eslint` |
| Test | `pytest` | `pytest` | `vitest` (+ Playwright for the final E2E test) |
| Deps | `pyproject.toml` (uv or pip) | `pyproject.toml` | `package.json` + lockfile committed |

Everyone: no secrets in code, no `print`/`console.log` left in merged code (use a logger), and
user-facing error messages in English for now.

---

## 9. Working in parallel without waiting (mocks)

| Person | Depends on | How they work before it's ready |
|---|---|---|
| **A** | Judge | Seed data includes some already-judged submissions (AC, PARTIAL, CE…) so scoring and the submissions list can be tested. Optional `backend/scripts/fake_judge.py` marks every PENDING as AC for demos. |
| **B** | Backend | Uses the DB directly: run `docker compose up db backend` (for migrations) or a test DB, then insert `PENDING` rows with SQL. Test programs live in `judge/samples/`. |
| **C** | Backend | `VITE_USE_MOCKS=true` uses MSW (Mock Service Worker) handlers in `src/mocks/` that return the **exact JSON from §6.2**. The mock submission goes PENDING → JUDGING → AC over 3 polls. Turning off mocks = changing one env var. |

Because every mock is copied from §6.2, switching to the real backend should not need code changes.

---

## 10. Git workflow & CI

### 10.1 Branches

- `main` — always runnable. Don't push to it directly; merge through a PR so CI runs.
- Feature branches: `<area>/<short-name>`, e.g. `backend/auth`, `judge/time-limits`, `frontend/problem-page`.
- Update your branch from `main` **at least every day you work**: `git pull --rebase origin main`.

### 10.2 Commits

Conventional commits: `feat(backend): add login endpoint`, `fix(judge): detect MLE`,
`docs: add java language`. Scopes: `backend`, `judge`, `frontend`, `docs`, `infra`.

### 10.3 Pull requests

- **No review approval needed** — merge your own PR once CI is green.
- Before merging: pull the latest `main` into your branch and run it locally once.
- Use squash merge so `main` stays readable.
- Post the PR link in the group chat when you merge, so the others know to pull.
- PR template (`.github/pull_request_template.md`):

```markdown
## What
## Why
## Checklist
- [ ] Only touches my folder (or I told the owner)
- [ ] Tests added/updated and passing locally
- [ ] `docker compose up --build` still works
- [ ] New env vars added to .env.example
- [ ] Changed a table/API field? Updated docs/ too
```

### 10.4 CI (`.github/workflows/ci.yml`)

Jobs run only when their folder changes (`paths:` filter), plus the integration job on every PR:

| Job | Runs |
|---|---|
| `backend` | `ruff check`, `pytest` against a Postgres service container |
| `judge` | `ruff check`, `pytest` (includes the verdict sample suite) — must run on Linux |
| `frontend` | `npm ci`, `eslint`, `tsc --noEmit`, `vitest`, `npm run build` |
| `compose` (integration) | `docker compose up -d --build --wait`, run `python3 scripts/smoke_test.py`, then `docker compose down -v` |

`scripts/smoke_test.py` (written by A in week 2, standard library only so it also runs on Windows):
log in as a seed student → submit the A+B solution → poll until final → assert `AC` and
`points_earned == max_points` in the problems list. Steps: [WEEK2_PLAN.md §6](WEEK2_PLAN.md).

---

## 11. Schedule & integration milestones

| When | Milestone | Who | Exit criteria |
|---|---|---|---|
| **Day 0** | **Skeleton** | A creates the first commit; then B, C add their stubs | Repo layout of §2, compose of §3.4, `.env.example`, PR template. `docker compose up` starts: db, backend `GET /api/health` → `{"status":"ok"}`, judge logs "waiting for jobs", frontend shows a blank layout. |
| **End of week 1** | **M1 — Basics in place** | All | A's first migration matches §4.2. C's mocks match §6.2. B's sample programs exist. |
| **End of week 2** | **M2 — Walking skeleton** (first real merge) | All | Real end-to-end on `main`: log in → open contest → submit A+B (C++) → judged AC → points shown. Mocks off. Smoke test in CI is green. |
| **End of week 3** | **M3 — MVP complete** | All | Everything in PLAN.md §1 works: all verdicts, partial scoring, Python, submissions tab, admin upload, sandbox with no network. §12 checklist passes. |
| **End of week 4** | **M4 — P1 features** | All | FEATURES.md F1–F8 merged and working on `main`. |
| **End of week 5** | **M5 — P2 features + feature freeze** | All | FEATURES.md F9–F16 merged. FEATURES.md §5 checklist passes. No new features after this. |
| **Week 6** | **M6 — Hardening & demo** | All | Both checklists (§12 + FEATURES.md §5) pass on a fresh clone. README explains setup in ≤ 5 commands. Demo data loaded. Stretch features (P3) only if all of this is done. |

**Integration session:** every week, one fixed 1-hour slot where all three run `main`
together, test the full flow, and file bugs as GitHub issues labeled `backend`/`judge`/`frontend`.

---

## 12. Final end-to-end acceptance checklist

Run on a **fresh clone** with `cp .env.example .env && docker compose up --build`:

- [ ] Wrong password shows an error; correct login goes to the contest list
- [ ] Contest page shows "Points earned: X / Max points: Y" and the problem table with colored levels
- [ ] Search filters problems; pagination and rows-per-page work; URL keeps `?search=&page=`
- [ ] Problem page shows statement, limits, samples; editor switches between C++ and Python
- [ ] Submissions get each verdict correctly: AC, WA, TLE, MLE, RE, CE, PARTIAL
- [ ] PARTIAL score = floor(max × passed / total); the problem shows the **best** score
- [ ] ✓ appears only when points earned = max points
- [ ] Submissions tab lists newest first; a click opens the details with per-test results / compile error
- [ ] A student cannot open another student's submission (404)
- [ ] A student gets 403 on `/api/admin/*`
- [ ] Submitting twice within 5 s → "please wait" message (429)
- [ ] User code cannot reach the internet (`curl`/socket test in a submission fails)
- [ ] An infinite loop / fork bomb does not freeze the judge; the next submission is still judged
- [ ] Admin creates a problem, uploads a zip of testcases, adds it to a contest → students see it and can solve it
- [ ] Killing the judge container during judging → after restart, the submission is judged again (stale recovery)

---

## 13. Day-0 checklist (do this together, ~1 hour)

1. **A**: create the skeleton (§2), `docker-compose.yml` (§3.4), `.env.example` (§3.2), `.gitignore`,
   backend stub with `/api/health`, push to `main`.
2. **All**: optionally turn on branch protection for `main` that only requires CI to pass
   (no reviews). Create the group chat channel for announcements.
3. **B**: branch `judge/skeleton` → Dockerfile with `g++` + `python3`, worker that connects to
   the DB and logs "waiting for jobs". Merge.
4. **C**: branch `frontend/skeleton` → Vite + React + TS app with the sidebar layout and MSW set up. Merge.
5. **All**: everyone clones `main`, runs `docker compose up --build`, and confirms all four services start.
6. Skim §4, §6, §7 together, then start coding.
