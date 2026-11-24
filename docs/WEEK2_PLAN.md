# Week 2 Plan — Walking Skeleton (M2)

**Dates:** Tue 24/11/2026 → Sun 29/11/2026 (integration session **Sat 28/11**, Sunday is buffer).
**Goal (M2, [MASTER_PLAN §11](MASTER_PLAN.md)):** on `main`, with mocks **off**, a real student can
log in → open contest `project120261` → open the A+B problem → submit C++ → the real judge returns
**AC** → the Problems table shows full points and ✓. The smoke test proves it in CI.

Specs this plan implements: [MASTER_PLAN.md](MASTER_PLAN.md) §3–§7. If this file and MASTER_PLAN
disagree, MASTER_PLAN wins — fix this file.

---

## 0. Where we start (end of week 1)

| Part | State on `main` |
|---|---|
| Repo / infra | Compose with 4 services, `.env.example`, CI (`backend` + `compose` jobs), PR template |
| Backend (A) | Config, error envelope, `/api/health`, all 7 MVP tables (migration `0001`), 14 tests, 95% coverage |
| Backend **carry-over** | Login, seed data, contests endpoints, `fake_judge.py` — not done yet |
| Judge (B) | Placeholder only (`judge/judge/main.py` logs and sleeps) |
| Frontend (C) | Placeholder only (static page served by `python -m http.server`) |

So week 2 is really "week 1 + week 2" for B and C, and A has 4 carry-over items. The plan below
puts **unblocking work first** in every column.

---

## 1. Shared decisions for this week (everyone reads this)

These close gaps that MASTER_PLAN leaves open. They are already reflected in the sections below.

| # | Decision | Owner |
|---|---|---|
| D1 | **Seed accounts** (dev only): `admin` / `admin123` (admin), `student1`, `student2`, `student3` / `123456` (students). Full names: `Admin`, `Nguyen Van A`, `Tran Thi B`, `Le Van C`. | A |
| D2 | **Seed contest:** `project120261`, "Project 1 - 2026.1", start `2026-09-01T00:00:00Z`, end `2027-01-15T00:00:00Z`, public. | A |
| D3 | **Seed problems** (5, all `easy`, 1000 ms, 256 MB) — see §2.3 for codes, points and I/O. | A writes, B checks the testcases with real solutions |
| D4 | **Seed runs on backend start** when `SEED_ON_START=true` (new env var, default `true` in `.env.example`). Seed is idempotent: upsert by `username` / `code`; testcase files are rewritten only when missing. | A |
| D5 | **Testcase storage becomes a named volume** `problems:` instead of the bind mount `./data/problems`. Reason: the backend runs as uid 10001; on Linux (CI) it cannot write into a host folder owned by another uid, so the seed would fail. A named volume takes the image's ownership. Backend mounts it read-write, judge read-only. `data/problems/` in git stays only as a placeholder. | A (compose), B (judge mount) |
| D6 | **Smoke test is Python, not bash:** `scripts/smoke_test.py`, standard library only (`urllib`, `json`), so it runs the same on Windows and in CI without `jq`. MASTER_PLAN §10.4 is updated to match (it used to say `smoke_test.sh`). | A writes, B + C review |
| D7 | **Integer division in seed problems:** A+B uses only **non-negative** `a`, `b` with `b > 0`, because C++ `/` and Python `//` differ on negatives. | A |
| D8 | **Frontend container:** `node:20-alpine`, `npm ci`, `npm run dev -- --host 0.0.0.0 --port 5173`. Vite reads `VITE_*` from the container environment (`env_file: .env`). | C |
| D9 | **Token storage:** JWT in `localStorage` under key `oj_token`. Acceptable because statements are rendered without raw HTML (PLAN.md §5 C.5). | C |
| D10 | **Frontend routes** (fixed, so A's smoke test and docs can link to them): `/login`, `/contests`, `/contests/:contestId?tab=problems\|submissions&search=&page=&size=`, `/contests/:contestId/problems/:problemId`, `/submissions/:submissionId`. | C |
| D11 | **Judge reads schema from A's migrations.** The judge never has its own `schema.sql`. Locally: `docker compose up -d db backend`. In CI: the `judge` job runs `cd backend && uv run alembic upgrade head` against its Postgres service before `pytest`. | B (CI job), A (helps) |
| D12 | **Branch names this week:** `backend/auth-seed`, `backend/contest-problems`, `backend/submit`, `infra/smoke-test`, `judge/worker`, `judge/limits`, `judge/ci`, `frontend/app-shell`, `frontend/contest-page`, `frontend/problem-page`, `frontend/real-api`. | All |

**Announce in the group chat** when you merge anything that changes compose, `.env.example`, CI
or `docs/` (MASTER_PLAN rule 2).

---

## 2. Person A — Backend & Database

Detailed per-file layout is in [PERSON_A.md](PERSON_A.md) §2. Order matters: B needs seed data
on disk, C needs login and contests first.

### 2.1 Day-by-day

| Day | Branch / PR | Tasks | Unblocks |
|---|---|---|---|
| **Tue 24** | `backend/auth-seed` | `security.py` (bcrypt hash/verify, JWT create/decode with `sub`, `role`, `exp` — `sub` must be a **string** (`str(user.id)`): PyJWT ≥ 2.10 rejects integer `sub`), `deps.py` (`get_current_user`, `require_admin`), `routers/auth.py` (`POST /auth/login`, `GET /auth/me`), `schemas/auth.py` | C: real login |
| **Wed 25** | `backend/auth-seed` (same PR) | `scripts/seed.py` + seed folder (§2.3) + `SEED_ON_START` in `entrypoint.sh` + named volume (D4, D5). Merge PR. | B: real problems + testcases on disk |
| **Wed 25** | `backend/contest-problems` | `pagination.py`, `GET /contests`, `GET /contests/{id}` | C: contest list |
| **Thu 26** | `backend/contest-problems` | `services/scoring.py`, `GET /contests/{id}/problems`, `GET /contests/{id}/problems/{pid}` (samples from files). Merge. | C: contest + problem pages |
| **Thu 26** | `backend/submit` | `POST .../submit`, `GET /contests/{id}/submissions`, `GET /submissions/{id}`, `scripts/fake_judge.py`. Merge. | B + C: real submissions to judge / poll |
| **Fri 27** | `infra/smoke-test` | `scripts/smoke_test.py` (D6), extend CI `compose` job to run it, README "Run it" update. | M2 proof |
| **Sat 28** | — | Integration session; fix what breaks. | M2 |

### 2.2 Endpoint details (beyond MASTER_PLAN §6.2)

**Auth**
- Login failure (unknown user **or** wrong password) → 401 `UNAUTHORIZED`, message
  `"Invalid username or password"`. Same message for both cases; run bcrypt even for an unknown
  user (against a dummy hash) so the response time doesn't reveal which usernames exist.
- Login request validation: `username` 1–50 chars, `password` 1–72 **bytes** (bcrypt ignores or
  rejects anything longer; bcrypt ≥ 4.1 raises an error) → otherwise 400 `VALIDATION_ERROR`.
- `get_current_user`: missing header, bad signature, expired token, or user no longer exists → 401.
  The 401 body must still be the error envelope (FastAPI's default `{"detail": ...}` is not allowed).
- `require_admin` → 403 `FORBIDDEN`.
- CORS: allow origins from `CORS_ORIGINS`, methods `GET, POST, PUT, PATCH, DELETE, OPTIONS`,
  header `Authorization, Content-Type`. Test one preflight request.

**Contests**
- List: students see `is_public = true` contests; admins see all. Sorted by `start_time DESC NULLS LAST, id DESC`.
- `problem_count` computed with a `COUNT` subquery, not per-row queries.
- Detail of a non-public contest for a student → 404 (not 403).

**Problems list** (`GET /contests/{id}/problems`)
- One query for the page rows, one for `total`, one for the two totals. The best scores come from
  one `GROUP BY problem_id` query on `submissions` filtered by `(user_id, contest_id)`
  (uses index `ix_submissions_user_contest_problem`).
- `search`: `ILIKE '%' || :q || '%'` on `title` or `code`. Escape `%` and `_` in the user input.
  Empty / whitespace search = no filter.
- `size` > 100 or `page` < 1 → 400 `VALIDATION_ERROR` (validated in `pagination.py`, shared by all lists).
- `total_points_earned` / `total_max_points` are over **all** problems of the contest, ignoring
  `search` and pagination.

**Problem detail**
- Problem not attached to this contest → 404.
- `samples`: testcases with `is_sample = true`, ordered by `order_index`, read from
  `PROBLEMS_DIR`. Cap each sample at 4 KB when returning. Missing file → skip that sample and log
  a warning (never 500).
- `languages`: from `app/constants.py` `LANGUAGES` (one source of truth).

**Submit**
- Order of checks: auth → contest visible + problem in contest (404) → `language` in `LANGUAGES`
  (400) → `source_code` not blank (400) → UTF-8 byte length ≤ `MAX_SOURCE_BYTES` (413) → cooldown (429).
- Cooldown: in the same transaction, `SELECT ... FROM users WHERE id = :uid FOR UPDATE`, then
  check the user's latest `submissions.created_at`. The row lock stops two parallel requests from
  both passing. The 429 message includes the seconds left: `"Please wait 3 s before submitting again"`.
- Insert with `max_points` copied from `contest_problems`, `status='PENDING'`. Return 201.
- Never touch `status` after insert (MASTER_PLAN §4.3).

**Submissions**
- List: current user's, newest first (`id DESC`), optional `problem_id` filter. Admins may pass
  `user_id`; a student passing `user_id` of someone else gets their **own** list (param ignored).
- Detail: owner or admin, otherwise 404. `results` joined with `testcases` to return
  `order_index`, sorted by it. While `PENDING`/`JUDGING`: `results: []`, `judged_at: null`.

**`scripts/fake_judge.py`**
- Claims with the **same SQL as MASTER_PLAN §7.1**, waits 1 s, writes `AC` with full score,
  `tests_passed = tests_total = number of testcases`, one `submission_results` row per testcase
  with `time_ms = 1`, `memory_kb = 1024`. Run with `docker compose exec backend python -m scripts.fake_judge`.
- **Never run it while the real judge is running** (both would claim jobs). It prints a warning on start.

### 2.3 Seed data (`data/seed/problems/`)

Folder per problem:

```
data/seed/problems/P_ADD_SUB_MUL_DIV/
├── problem.yaml        # code, title, level, time_limit_ms, memory_limit_mb, max_points, order_index, sample_count
├── statement.md
├── tests/1.in 1.out 2.in 2.out ...     # LF line endings (.gitattributes: data/seed/** text eol=lf)
└── solutions/
    ├── ac.cpp  ac.py                   # must get AC — used by the smoke test and by B
    └── wa.cpp                          # optional: must NOT get AC
```

| order | Code | Title | Points | Tests (samples) | I/O |
|---|---|---|---|---|---|
| 1 | `P_ADD_SUB_MUL_DIV` | Week 1 - Add Subtract Multiplication Division of A and B | 100 | 10 (1) | `a b` (0 ≤ a ≤ 10⁹, 1 ≤ b ≤ 10⁹) → `a+b`, `a-b`, `a*b`, `a/b` (integer), one per line. Needs 64-bit. |
| 2 | `P_HHMMSS_TO_SECONDS` | Week 1 - Convert hh:mm:ss to seconds | 140 | 10 (1) | `hh:mm:ss` → total seconds |
| 3 | `P_UPPERCASE_TEXT` | Week 1 - Convert a text to uppercase | 100 | 8 (1) | lines of text until EOF → same lines uppercased |
| 4 | `P_SUM_OF_ARRAY` | Week 1 - Sum of an array | 120 | 10 (2) | `n` then `n` integers (n ≤ 10⁶) → sum. Large tests catch slow I/O. |
| 5 | `P_MAX_OF_THREE` | Week 1 - Max of three numbers | 100 | 6 (1) | `a b c` → max |

Seed also inserts **3 already-judged submissions for `student2`** with matching
`submission_results`: `P_MAX_OF_THREE` → `AC` 100/100 (6/6), `P_ADD_SUB_MUL_DIV` → `PARTIAL`
70/100 (7/10, tests 8–10 `WA`), `P_HHMMSS_TO_SECONDS` → `CE` 0/140 with a short g++ error in
`compile_output` and no results. They are inserted only if `student2` has no submissions yet, so C has real non-AC data and
A can test scoring before the judge works. `student1` has **no** submissions, so the smoke test
starts from 0 points.

The seed is idempotent and does **not** delete existing submissions. `docker compose down -v`
resets everything.

### 2.4 Tests A adds this week

| File | Covers |
|---|---|
| `test_security.py` | hash/verify, token round-trip, expired token, tampered token |
| `test_auth.py` | login OK, wrong password, unknown user (same message), `/me` with/without token, 401 envelope shape |
| `test_pagination.py` | defaults, `size` cap, `page < 1` |
| `test_contests.py` | list for student vs admin, private contest 404, `problem_count` |
| `test_problems.py` | search (incl. `%`/`_`), pagination, totals over all problems, best-of score, `is_complete`, samples, problem not in contest 404 |
| `test_submit.py` | 201 + PENDING row, bad language 400, blank 400, 413, 429 with seconds left, max_points snapshot |
| `test_submissions.py` | own list newest first, `problem_id` filter, other student's detail 404, admin can see all, PENDING shape |
| `test_seed.py` | running the seed twice gives the same row counts |

Coverage stays ≥ 80% (`uv run pytest --cov=app`).

### 2.5 A — done when

- [ ] Every endpoint above returns exactly the JSON of MASTER_PLAN §6.2 (checked in Swagger)
- [ ] `docker compose down -v && docker compose up --build` → seed loaded, `student1` can log in
- [ ] Seed testcase files exist inside the judge container: `docker compose exec judge ls /data/problems/1/tests`
- [ ] `fake_judge.py` turns a PENDING submission into AC
- [ ] `scripts/smoke_test.py` passes locally and in CI
- [ ] Posted "`<endpoint>` is live on main" in the chat for each merge

---

## 3. Person B — Judge

B starts from the placeholder. Week 2 target: **correct verdicts and scores** for C++ and Python,
with time and memory limits. Hard sandboxing (fork bombs, no reading testcase outputs, separate
uid) is week 3.

### 3.1 Code layout

```
judge/
├── Dockerfile               # python:3.12-slim + g++ ; non-root user
├── pyproject.toml / uv.lock # psycopg[binary] 3, pyyaml, pytest, ruff
├── languages.yaml           # MASTER_PLAN §7.4
├── judge/
│   ├── main.py              # startup: wait for DB, recover stale, loop
│   ├── config.py            # env vars (MASTER_PLAN §3.2, judge section)
│   ├── db.py                # connect with retry, claim_submission(), load_problem(), save_result()
│   ├── languages.py         # load + validate languages.yaml
│   ├── runner.py            # compile(), run_one() → RunResult(exit, signal, time_ms, memory_kb, stdout)
│   ├── compare.py           # normalize + compare (MASTER_PLAN §7.3)
│   └── verdict.py           # per-test verdict, final status, score (MASTER_PLAN §7.2)
├── samples/
│   ├── cpp17/  ac.cpp wa.cpp tle.cpp mle.cpp re.cpp ce.cpp
│   └── python3/ ac.py wa.py tle.py mle.py re.py ce.py
└── tests/
```

Pure functions (`compare.py`, `verdict.py`) have no DB and no subprocess, so they are fast to test.

### 3.2 Day-by-day

| Day | Branch / PR | Tasks |
|---|---|---|
| **Tue 24** | `judge/worker` | Real `Dockerfile` (`apt-get install -y --no-install-recommends g++`), `pyproject.toml`, `config.py`, `db.py` connect-with-retry (DB or tables not ready → log + retry every 2 s, never crash), `claim_submission()` with the exact SQL of §7.1, stale recovery at startup + every 60 s. `compare.py` + `verdict.py` + their unit tests. |
| **Wed 25** | `judge/worker` | `languages.py`, `runner.py`: temp dir per submission (`tempfile.mkdtemp`, always deleted in `finally`), write source, compile with `JUDGE_COMPILE_TIMEOUT_SECONDS`, run one test with stdin from the `.in` file. Full loop: claim → load problem + testcases → compile → run all → save in **one transaction**. Merge once a hand-inserted PENDING row gets AC/WA correctly. |
| **Thu 26** | `judge/limits` | Time limit (TLE), memory limit (MLE), output cap, RE detection — rules in §3.3. `SE` on any unexpected exception. |
| **Fri 27** | `judge/ci` | `samples/` for both languages, `tests/test_samples.py` runs every sample through `runner` + `verdict`. Add the `judge` job to CI (D11). Check all 5 seed problems with A's `solutions/ac.*` → AC. |
| **Sat 28** | — | Integration session. |

### 3.3 Judge rules to implement this week

**Running one test** (`subprocess.Popen` with `preexec_fn` setting the limits below, then
`os.wait4(proc.pid, 0)` to get exit status **and** `rusage` — do not also call `proc.wait()`, the
child can only be reaped once; read stdout in a thread so a full pipe can't deadlock). Limits are
set only on the **run** step, never on the compiler (g++ needs more memory than the problem limit).

| Limit | How | Verdict |
|---|---|---|
| Time | `RLIMIT_CPU` = ceil(limit s) + 1, **and** a wall-clock timer of `2 × time_limit_ms` that kills the process (catches `sleep`/blocking reads). CPU time = `ru_utime + ru_stime` from `wait4`. | CPU time > `time_limit_ms` or killed by the wall timer → `TLE` |
| Memory | `RLIMIT_AS` = `memory_limit_mb + 64 MB` slack (C++ runtime and Python interpreter need it). Peak memory = `ru_maxrss` (KB) from `wait4`. | `ru_maxrss > memory_limit_mb × 1024`, **or** the process failed and stderr contains `MemoryError` / `std::bad_alloc` → `MLE` |
| Output | Read stdout in chunks; stop and kill at `JUDGE_MAX_OUTPUT_BYTES`. | Output too large → `WA` (log it) |
| Stack | `RLIMIT_STACK` = memory limit (deep recursion is common in student code). | — |
| Crash | Non-zero exit code or killed by a signal (SIGSEGV, SIGFPE, SIGABRT…). | `RE` |

Check order for one test: TLE → MLE → RE → compare output (AC/WA). Store `time_ms` as CPU time
capped at the limit, `memory_kb` = `ru_maxrss`.

**Compile:** `CE` if exit ≠ 0 **or** the compile timeout hits. `compile_output` = stderr cut to
10 KB. Python has no compile step (a syntax error shows up as `RE` on every test — this matches
MASTER_PLAN; do **not** add `py_compile` this week, write it down as a week-3 option).

**Writing results:** one transaction: insert all `submission_results`, then update `submissions`
(`status`, `score`, `tests_passed`, `tests_total`, `time_ms`, `memory_kb`, `compile_output`,
`judged_at = now()`), with `WHERE id = :id AND status = 'JUDGING'`. If 0 rows are updated
(stale recovery gave the job to someone else), roll back and log.

**Errors:** any exception while judging one submission → set `SE`, `score = 0`, log the stack
trace, continue the loop. 0 testcases → `SE`. Missing testcase file → `SE`.

**Logging:** one line per submission: `id`, language, final status, score, total ms.

### 3.4 Tests B adds this week

| File | Covers | Needs |
|---|---|---|
| `test_compare.py` | CRLF, trailing spaces/tabs, trailing blank lines, a real difference, empty output | nothing |
| `test_verdict.py` | all 5 final-status rules, score floor, max time/memory, CE, SE | nothing |
| `test_languages.py` | yaml loads, unknown language rejected | nothing |
| `test_samples.py` | each `samples/<lang>/<verdict>.*` gives that verdict on a tiny problem in a temp dir | `g++`, `python3` (Linux) |
| `test_db.py` | claim takes one job, two claims never return the same id, stale reset, result transaction | Postgres with A's migrations (D11); skipped without `TEST_DATABASE_URL` |

CI `judge` job steps: Postgres service → `setup-uv` → `cd backend && uv sync --frozen && uv run alembic upgrade head`
(with `DATABASE_URL` pointing at the service) → `cd judge && uv sync --frozen && uv run ruff check . && uv run pytest`.
The Ubuntu runner already has `g++` and `python3`.

On Windows, run the judge tests inside the container:
`docker compose run --rm judge python -m pytest` (the image must include the tests and dev deps,
or B adds a `test` target to the Dockerfile).

### 3.5 B — done when

- [ ] Insert a PENDING row by SQL → final verdict within 3 s, for all 6 samples × 2 languages
- [ ] `docker compose stop judge` mid-judging, start again → the job goes back to PENDING after `JUDGE_STALE_AFTER_SECONDS` and is judged
- [ ] One `SE` does not stop the worker; the next submission is judged
- [ ] All 5 seed problems: `solutions/ac.cpp` and `ac.py` → AC with full score
- [ ] `judge` CI job is green
- [ ] Judge container still has no internet (`networks: [internal]`) and mounts the problems volume read-only

---

## 4. Person C — Frontend

C starts from the placeholder. Week 2 target: every MVP student page exists, works on mocks, and
works with mocks off on Saturday. Admin forms and the full submission detail page are week 3.

### 4.1 Stack

| Concern | Choice | Notes |
|---|---|---|
| App | Vite + React 18 + TypeScript (strict) | `npm create vite@latest frontend -- --template react-ts` |
| UI | MUI v6 | Matches the HUSTack screenshot style |
| Routing | `react-router-dom` v6 | Routes in D10 |
| Server state | TanStack Query v5 | `refetchInterval` for polling |
| Mocks | MSW v2 | `VITE_USE_MOCKS=true` → start worker before render |
| Editor | `@monaco-editor/react` + local `monaco-editor` | Configure `loader.config({ monaco })` so it does **not** load from a CDN |
| Markdown | `react-markdown` + `remark-gfm` | No `rehype-raw` (no raw HTML) |
| Tests | Vitest + Testing Library | Playwright comes in week 6 |
| Lint/format | ESLint + Prettier | |

### 4.2 Code layout

```
frontend/src/
├── api/
│   ├── client.ts       # fetch wrapper: base URL, Bearer token, error envelope → ApiError, 401 handling
│   ├── types.ts        # hand-written from MASTER_PLAN §6.2, field for field (snake_case)
│   └── endpoints.ts    # login(), me(), listContests(), getContest(), listProblems(), getProblem(), submit(), listSubmissions(), getSubmission()
├── mocks/
│   ├── browser.ts
│   ├── handlers.ts     # one handler per endpoint, JSON copied from §6.2
│   └── data.ts         # 5 seed-like problems, 1 contest, a few submissions
├── auth/               # AuthProvider, useAuth, RequireAuth
├── components/         # Layout (sidebar + top bar), LevelChip, StatusChip, Pagination…
├── pages/              # LoginPage, ContestListPage, ContestPage (+ tabs), ProblemPage, SubmissionPage
└── main.tsx
```

### 4.3 Day-by-day

| Day | Branch / PR | Tasks |
|---|---|---|
| **Tue 24** | `frontend/app-shell` | Vite app replaces `frontend/placeholder/` (delete it). Dockerfile (D8), `.dockerignore` (`node_modules`). Layout: left sidebar (Home, Programming Contests, Learning), top bar (logo, language switch placeholder, user menu + logout). Router with all D10 routes (empty pages). `api/client.ts`, `api/types.ts`, MSW set up with **all** §6.2 handlers. Merge — compose must still start. |
| **Wed 25** | `frontend/contest-page` | Login page + `AuthProvider` (token in `localStorage`, D9; `GET /auth/me` on load; `RequireAuth` redirects to `/login?next=…`). Contest list page. |
| **Thu 26** | `frontend/contest-page` | Contest page: "Points earned: X / Max points: Y", **Problems** tab (search box with 300 ms debounce, table: Problem link, Code, Level chip Easy=green/Medium=orange/Hard=red, Points earned, Max points, ✓; rows-per-page 5/10/25 + pagination; all state in the URL) and **Submissions** tab (time, problem, language, status chip, score; row click → `/submissions/:id`). Merge. |
| **Fri 27** | `frontend/problem-page` | Problem page: Markdown statement, time/memory limits, samples with copy buttons, language dropdown (from `languages`), Monaco editor (C++ / Python mode), Submit. After submit → navigate to `/submissions/:id`. **Minimal** submission page: polls `GET /submissions/{id}` every 1.5 s while `PENDING`/`JUDGING`, then shows status, score, tests passed, and compile output if `CE`. Merge. |
| **Sat 28** | `frontend/real-api` | Integration session: run with `VITE_USE_MOCKS=false`, fix any field mismatch (fix the **mock** or ask A — never add a converter). Add `frontend` CI job. |

### 4.4 Behaviour details

- **Errors:** `client.ts` parses the error envelope into `ApiError { status, code, message }`.
  401 on any call except login → clear token, redirect to `/login?next=<current path>`.
  429 on submit → show the server message in a snackbar and keep the code in the editor.
  413 → "Source code is too large (max 64 KB)". Other errors → snackbar with `message`.
- **Submit button:** disabled while the request is in flight (no double submit).
- **Polling:** stop when status is final, when the page unmounts, and when the tab is hidden
  (TanStack Query does this with `refetchIntervalInBackground: false`). After a final status,
  invalidate the problems-list query so points update when the user goes back.
- **Dates:** API is UTC; display in the browser's local time (`Intl.DateTimeFormat`).
- **Mocks must match §6.2 exactly.** The mock submission goes PENDING → JUDGING → AC over 3
  polls (MASTER_PLAN §9). Mock login accepts the seed accounts from D1.
- **Local dev without Docker:** Vite reads `frontend/.env.development` (not the root `.env`).
  C commits that file with `VITE_API_BASE_URL=http://localhost:8000/api` and `VITE_USE_MOCKS=true`
  (no secrets in it). The compose image has no hot reload; use `npm run dev` locally while coding.
- **Accessibility basics:** form labels, buttons with text, table headers, focus visible.

### 4.5 Tests C adds this week

| Test | Covers |
|---|---|
| `client.test.ts` | Bearer header added, error envelope parsed, 401 triggers logout |
| `LoginPage.test.tsx` | wrong password shows message, success redirects to `next` |
| `ProblemsTab.test.tsx` (with MSW) | rows render, search updates URL, ✓ only when complete, level colors |
| `SubmissionPage.test.tsx` (with MSW) | polls until AC, shows compile output for CE |

### 4.6 C — done when

- [ ] `VITE_USE_MOCKS=true`: every page works with no backend running
- [ ] `VITE_USE_MOCKS=false` + compose: log in as `student1` → submit A+B → see AC → Problems tab shows 100/100 ✓
- [ ] URL keeps `?tab=&search=&page=&size=`; reload restores the same view
- [ ] Statement Markdown with `<script>` in it is shown as text, not run
- [ ] `frontend` CI job green: `npm ci`, `eslint`, `tsc --noEmit`, `vitest run`, `npm run build`

---

## 5. Shared files changed this week

| File | Change | By | When |
|---|---|---|---|
| `docker-compose.yml` | named volume `problems:` (D5); judge mounts it `:ro` | A | Wed 25 |
| `.env.example` | `SEED_ON_START=true` | A | Wed 25 |
| `.gitattributes` | `data/seed/** text eol=lf` | A | Wed 25 |
| `.github/workflows/ci.yml` | `judge` job (B, Fri), `frontend` job (C, Sat), smoke test step in `compose` job (A, Fri) | A, B, C | — |
| `scripts/smoke_test.py` | new (D6) | A | Fri 27 |
| `README.md` | seed accounts, how to run tests per folder, `fake_judge` usage | A, B, C (own section each) | by Sat 28 |
| `docs/MASTER_PLAN.md` | §3.3 volume, §3.2 `SEED_ON_START`, §10.4 smoke test file name | done with this plan | — |

To avoid conflicts in `ci.yml`: each person adds **their own job block** only, and pulls `main`
right before editing it.

---

## 6. Smoke test (`scripts/smoke_test.py`)

Run **from the repo root** (it reads the solution file by relative path) after
`docker compose up -d --build --wait`. Base URL from `SMOKE_API_URL`
(default `http://localhost:8000/api`). Exit code 0 = pass.

1. `GET /health` until 200 (max 60 s).
2. `POST /auth/login` as `student1` / `123456`.
3. `GET /contests` → find `project120261`.
4. `GET /contests/{id}/problems?search=P_ADD_SUB_MUL_DIV` → problem id, `max_points`.
5. `POST .../submit` with `data/seed/problems/P_ADD_SUB_MUL_DIV/solutions/ac.cpp`.
6. Poll `GET /submissions/{id}` every 1 s, max 60 s, until status is final.
7. Assert `status == "AC"` and `score == max_points`.
8. `GET /contests/{id}/problems?search=P_ADD_SUB_MUL_DIV` → assert `points_earned == max_points` and `is_complete`.
9. Print a one-line summary; on failure print the last response body.

CI `compose` job: after `up --wait`, run `python3 scripts/smoke_test.py`; on failure, print
`docker compose logs`. Because the 5 s cooldown is per user, the smoke test submits **once**.

---

## 7. Dependencies and fallbacks

| If this is late… | …the others do this |
|---|---|
| A's login (Tue) | C keeps mocks; B is not affected |
| A's seed (Wed) | B inserts a test problem + testcases by SQL and files in a temp dir (tests don't need seed) |
| A's submit endpoint (Thu) | B inserts PENDING rows by SQL; C keeps the submit mock |
| B's judge (Fri) | A + C demo with `fake_judge.py`; M2 is then "partial" — record it in the week-2 report |
| C's pages (Fri) | A + B demo the flow with Swagger + `smoke_test.py` |

Nobody waits: everyone builds against the spec, and the mocks/fake judge cover the gaps
(MASTER_PLAN §9).

---

## 8. Integration session — Sat 28/11 (1–2 hours, all three)

1. Everyone: `git pull`, `docker compose down -v`, `cp .env.example .env` (if new vars), `docker compose up --build`.
2. Check: 4 services up, seed loaded, judge log shows "waiting for jobs".
3. C switches `VITE_USE_MOCKS=false`. Walk the M2 flow in the browser as `student1`.
4. Try each verdict with B's samples through the UI (WA, TLE, MLE, RE, CE, PARTIAL).
5. Try: wrong password, submit twice fast (429), open `student2`'s submission as `student1` (404).
6. Run `python scripts/smoke_test.py`.
7. Every bug → GitHub issue labeled `backend` / `judge` / `frontend`, assigned, fixed by Sunday or moved to week 3.
8. Write the week-2 report (`docs/reports/WEEK2_REPORT.md`, Vietnamese, for the teacher).

---

## 9. M2 exit checklist

- [ ] `main` on a fresh clone: `cp .env.example .env && docker compose up --build` starts all 4 services
- [ ] `student1` logs in through the real UI (mocks off)
- [ ] Contest page shows "Points earned: 0 / Max points: 560" before the first submission
- [ ] Submitting `ac.cpp` for A+B → PENDING → JUDGING → AC within 10 s, shown on the submission page
- [ ] Problems tab then shows 100 / 100 ✓ and the summary updates
- [ ] `ac.py` also gets AC; a WA program gets `WA` (or `PARTIAL` with the right score)
- [ ] `student2`'s seeded PARTIAL submission shows 70/100 in their Problems tab
- [ ] CI on `main`: `backend`, `judge`, `frontend`, `compose` (with smoke test) all green
- [ ] Week-2 report written

---

## 10. Risks this week

| Risk | Impact | Mitigation |
|---|---|---|
| B and C each have ~2 weeks of work in one week | M2 slips | Day-by-day order above puts the M2 path first; nice-to-haves (copy buttons, debounce, rows-per-page) can slip to Monday |
| Windows dev machines can't run the judge natively | B can't test | Always run the judge in Docker (`docker compose run --rm judge …`); CI on Linux is the reference |
| Seed volume permissions on Linux | CI seed fails | D5 (named volume) |
| `RLIMIT_AS` too tight for Python / C++ runtime | False MLE/RE on AC code | 64 MB slack; check with seed `ac.py` on the 10⁶-number test |
| Python slow on `P_SUM_OF_ARRAY` with `input()` | False TLE | The seed `ac.py` uses `sys.stdin.buffer.read()`; statement mentions fast input |
| Monaco loads from a CDN by default | Editor blank offline / in demo | §4.1: `loader.config({ monaco })` |
| `fake_judge.py` and the real judge both running | Jobs judged twice / wrong verdicts | Only run `fake_judge` when the judge container is stopped; it warns on start |
| `ci.yml` edited by 3 people | Merge conflicts | Each adds only their own job; pull before editing |
| Known gap: user code runs as the judge user and can read `/data/problems/**/*.out` | Cheating possible | **Week 3** sandbox task for B: run user code as a separate uid with no read access to the problems volume (input passed only via stdin). Not blocking M2. |

---

## 11. Moved to week 3 (on purpose)

- A: admin endpoints (create contest/problem, zip upload, attach), error-handling pass.
- B: process-count limit (fork bomb), separate run uid, read-only root filesystem, `py_compile` option, verdict suite in CI for every edge case.
- C: full submission detail page (per-test table, source view), admin forms, empty/loading/error states polish.
