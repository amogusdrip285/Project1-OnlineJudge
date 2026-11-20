# Online Judge — MVP Plan

A small online judge like HUSTack: students open a contest, see a list of problems with points,
submit code, and get a verdict and score. Build this first, then add features.

---

## 1. MVP scope

**In scope (v1)**
- Log in (student / admin roles)
- Contest list → contest page with two tabs: **Problems** and **Submissions**
- Problem table: name, code, level (Easy/Medium/Hard), points earned, max points, complete ✓
- "Points earned: X / Max points: Y" summary, search box, pagination
- Problem detail page: statement, sample input/output, code editor, language picker, Submit
- Judge: compile + run against hidden testcases, time/memory limits, verdicts
- Partial scoring: `score = max_points × passed_tests / total_tests`; a problem's score is the
  user's **best** submission
- Admin: create contest, create problem, upload testcases (zip of `1.in/1.out, 2.in/2.out…`)

**Out of scope for v1 (later)**
Leaderboard/ranking, real-time updates over WebSocket, plagiarism checking, special checkers,
interactive problems, contest timers/freezes, more languages, email, i18n (ENG/VI switch).

**Languages for v1:** C++17 and Python 3. Add Java/C later.

---

## 2. Suggested stack

Pick one stack and keep it. This is a suggestion; swap pieces if the team knows something else
better.

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Vite + TypeScript, MUI or Tailwind, Monaco editor | The screenshot is a MUI-style table; Monaco is the VS Code editor |
| Backend API | Python FastAPI (or Node/Express) | Fast to write, auto-generated API docs at `/docs` |
| Database | PostgreSQL | Also used as the job queue (no Redis needed in v1) |
| Judge worker | Python service running in a Docker container | Simple to sandbox and isolate |
| Run everything | `docker compose up` | Same setup on every teammate's machine |

> Windows note: the judge uses Linux features (`ulimit`, `setrlimit`, cgroups). Run it in Docker
> or WSL, not natively on Windows.

---

## 3. Architecture

```
 Browser (React)
     │  REST/JSON  (+ JWT in Authorization header)
     ▼
 Backend API (FastAPI) ──── PostgreSQL ◄──── Judge Worker(s)
     │                         ▲   polls PENDING submissions,
     │ saves testcase files    │   writes verdict + score back
     ▼                         │
 /data/problems/<id>/tests  ◄──┘   (shared Docker volume, read-only for worker)
```

- The frontend talks **only** to the backend.
- The backend never runs user code. It inserts a submission with status `PENDING` and returns.
- The judge worker picks up `PENDING` rows, runs them, and writes results to the DB.
- The frontend polls `GET /api/submissions/{id}` every 1–2 s until the status is final.

This means the three parts only meet at the **database schema** and the **REST API**. Agree on
those in week 1, and everyone can then work in parallel.

---

## 4. Shared specs

> **Summary only.** The detailed version (exact SQL, exact JSON, judge rules) is in
> [MASTER_PLAN.md](MASTER_PLAN.md).

### 4.1 Database schema

```sql
users        (id, username UNIQUE, password_hash, full_name, role['student'|'admin'], created_at)

contests     (id, code UNIQUE, title, description, start_time, end_time, is_public, created_at)

problems     (id, code UNIQUE, title, statement_md, level['easy'|'medium'|'hard'],
              time_limit_ms, memory_limit_mb, created_at)

contest_problems (contest_id, problem_id, max_points, order_index,
                  PRIMARY KEY (contest_id, problem_id))

testcases    (id, problem_id, order_index, input_path, output_path, is_sample BOOLEAN)

submissions  (id, user_id, contest_id, problem_id, language['cpp17'|'python3'],
              source_code, status, score, max_points,
              tests_passed, tests_total, time_ms, memory_kb,
              compile_output TEXT NULL, created_at, judged_at NULL)

submission_results (submission_id, testcase_id, verdict, time_ms, memory_kb)
```

### 4.2 Submission status / verdicts

| Code | Meaning |
|---|---|
| `PENDING` | Waiting in queue |
| `JUDGING` | A worker has picked it up |
| `AC` | Accepted (all tests passed) |
| `WA` | Wrong Answer |
| `TLE` | Time Limit Exceeded |
| `MLE` | Memory Limit Exceeded |
| `RE` | Runtime Error (non-zero exit / crash) |
| `CE` | Compilation Error |
| `PARTIAL` | Some tests passed (score > 0, not all AC) |
| `SE` | System Error (judge bug, not the user's fault) |

Final status = `AC` if all pass, `CE` if compile fails, otherwise `PARTIAL` if ≥1 test passed,
otherwise the verdict of the first failed test.

### 4.3 REST API (all under `/api`, JSON, JWT auth)

| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/auth/login` | all | `{username, password}` → `{token, user}` |
| GET | `/auth/me` | all | Current user |
| GET | `/contests` | all | List contests visible to user |
| GET | `/contests/{id}` | all | Contest info |
| GET | `/contests/{id}/problems?search=&page=&size=` | all | Rows for the Problems table, **including** `points_earned`, `max_points`, `is_complete` for the current user, plus `total_points_earned`, `total_max_points` |
| GET | `/contests/{id}/problems/{pid}` | all | Statement, limits, sample tests |
| POST | `/contests/{id}/problems/{pid}/submit` | all | `{language, source_code}` → `{submission_id}` |
| GET | `/contests/{id}/submissions?page=&size=` | all | Current user's submissions in this contest |
| GET | `/submissions/{id}` | owner/admin | Status, score, per-test results, compile output |
| POST | `/admin/contests` | admin | Create contest |
| POST | `/admin/problems` | admin | Create problem |
| POST | `/admin/problems/{pid}/testcases` | admin | Upload zip of testcases |
| POST | `/admin/contests/{id}/problems` | admin | `{problem_id, max_points, order_index}` |

Error envelope for every endpoint: `{ "error": { "code": "NOT_FOUND", "message": "..." } }`.

Exact sample JSON for every endpoint is in [MASTER_PLAN.md §6.2](MASTER_PLAN.md) so the
frontend can start with mock data before the backend is ready.

---

## 5. Work split

### 👤 Person A — Backend API & Database

**Owns:** `backend/`, DB migrations, auth, all REST endpoints, seed data.

Tasks
1. Project setup: FastAPI, SQLAlchemy, Alembic migrations, `docker-compose.yml` with Postgres.
2. Implement schema (4.1) as migrations. Seed script: 1 admin, 3 students, 1 contest, 5 problems
   with testcases (e.g. the "Week 1" problems: A+B, convert hh:mm:ss to seconds, uppercase text…).
3. Auth: bcrypt password hashing, JWT login, `require_user` / `require_admin` dependencies.
4. Contest + problem read endpoints, with search and pagination.
5. Scoring query: for each problem in a contest, `MAX(score)` of the user's submissions →
   points earned, complete = `points_earned == max_points`.
6. Submit endpoint: validate language, cap source size (e.g. 64 KB), rate-limit (e.g. 1 submit
   / 5 s per user), insert `PENDING` row.
7. Admin endpoints: create contest/problem, upload testcase zip → unzip safely into
   `/data/problems/<id>/tests/` (reject `..` paths and absolute paths in the zip).
8. Tests: pytest for auth, scoring, submit validation, permissions (a student must not see
   other students' code).

Definition of done: every endpoint in 4.3 works in Swagger UI (`/docs`) against seeded data.

---

### 👤 Person B — Judge Worker (code execution)

**Owns:** `judge/`, its Dockerfile, language configs, sandboxing.

Tasks
1. Worker loop: poll Postgres for one `PENDING` row, mark it `JUDGING` atomically:
   ```sql
   UPDATE submissions SET status='JUDGING'
   WHERE id = (SELECT id FROM submissions WHERE status='PENDING'
               ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)
   RETURNING *;
   ```
   This lets you run several workers later without two of them taking the same job.
2. Language config (data, not if/else):
   ```yaml
   cpp17:   { file: main.cpp, compile: "g++ -O2 -std=c++17 main.cpp -o main", run: "./main" }
   python3: { file: main.py,  compile: null, run: "python3 main.py" }
   ```
3. For each submission: make a temp dir → write source → compile (time limit ~10 s, capture
   stderr into `compile_output`) → run each testcase with stdin from `N.in`, capture stdout.
4. Limits per run: wall-clock timeout (`time_limit_ms`), memory limit (`setrlimit RLIMIT_AS`
   or Docker `--memory`), output size cap (e.g. 16 MB), process count cap (fork bombs).
5. Output comparison: ignore trailing whitespace on each line and trailing blank lines.
6. Compute verdict per test, final status, and `score = max_points × passed / total`. Write
   `submission_results` + update `submissions` in a single transaction.
7. Sandbox (step by step):
   - v1: worker runs in its own Docker container with **no network**, non-root user, read-only
     testcase volume, and each run uses its own temp dir.
   - v2: run each submission with `isolate` or `nsjail` for stronger isolation.
8. Mark `SE` and log the error if anything inside the judge crashes, so one bad job never kills
   the worker.
9. Tests: a folder of sample programs that **must** produce each verdict — AC, WA, TLE
   (infinite loop), MLE (huge array), RE (divide by zero / segfault), CE (syntax error).

Definition of done: insert a `PENDING` row by hand → it gets the right verdict within a few
seconds, for all 6 sample programs in both languages.

---

### 👤 Person C — Frontend (React)

**Owns:** `frontend/`.

Tasks
1. Vite + React + TS setup, router, layout: left sidebar (Home, Programming Contests,
   Learning), top bar (logo, language switch placeholder, avatar/logout).
2. API client with the JWT attached, plus a 401 → redirect-to-login handler. Start with
   **mock data** copied from MASTER_PLAN.md §6.2; switch to the real API when Person A is ready.
3. Pages:
   - **Login**
   - **Contest list**
   - **Contest detail** with tabs:
     - *Problems*: the "Points earned / Max points" summary, search box, table (Problem link,
       Code, Level colored Easy=green / Medium=orange / Hard=red, Points earned, Max points,
       ✓ if complete), rows-per-page selector + pagination
     - *Submissions*: table of the user's submissions (time, problem, language, status,
       score), status colored, click → submission detail
   - **Problem detail**: Markdown statement, limits, sample I/O with copy buttons, Monaco
     editor, language dropdown, Submit button
   - **Submission detail**: polls every 1.5 s while `PENDING/JUDGING`; then shows the verdict,
     score, per-test table, and compile errors if CE
   - **Admin (simple forms)**: create contest, create problem, upload testcase zip, attach
     problem to contest
4. Keep search + page in the URL (`?search=add&page=2`) so links can be shared.
5. Render statements safely: Markdown renderer with HTML disabled/sanitized (no
   `dangerouslySetInnerHTML` on raw input).

Definition of done: a student can log in, open a contest, submit A+B, watch it go
PENDING → AC, and see the points update in the Problems table.

---

## 6. Timeline (MVP = weeks 1–3 of 6)

| Week | Person A (Backend) | Person B (Judge) | Person C (Frontend) |
|---|---|---|---|
| 1 | **All together:** agree on schema, API, verdicts, sample JSON. Repo + docker-compose skeleton. | | |
| 1 | Migrations, seed data, login | Worker loop, run C++/Python without limits | Layout, routing, login page with mocks |
| 2 | Contest/problem/submit endpoints | Time/memory limits, verdicts, scoring | Contest page (both tabs), problem page + editor |
| 3 | Admin endpoints, testcase upload, scoring query | Docker sandbox, no network, verdict test suite | Submission detail + polling, admin forms, switch to real API |
| 4–5 | Features from [FEATURES.md](FEATURES.md) | | |
| 6 | **All together:** end-to-end testing, fix bugs, demo data, README, presentation | | |

---

## 7. Repo layout

```
Project1-OnlineJudge/
├── docker-compose.yml        # postgres, backend, judge, frontend
├── docs/
│   ├── PLAN.md               # this file
│   ├── MASTER_PLAN.md        # DB/API/judge specs, conventions, git workflow
│   └── FEATURES.md           # features for weeks 4–6
├── backend/                  # Person A
├── judge/                    # Person B
│   └── samples/              # programs for each verdict
├── frontend/                 # Person C
└── data/problems/            # testcases (gitignored except seed problems)
```

## 8. Team rules

- One branch per feature (`feat/backend-auth`, `feat/judge-limits`, `feat/fe-problem-page`),
  merge into `main` through a PR once CI passes (no review needed).
- Changing the schema or the API? Update `docs/` in the **same PR** and tell the others.
- Keep secrets (DB password, JWT secret) in `.env`. Commit only `.env.example`.
- `main` must always run with `docker compose up`.

## 9. After the MVP

See [FEATURES.md](FEATURES.md): 16 features planned for weeks 4–5, with owners and DB/API changes, and
4 stretch features for week 6.
