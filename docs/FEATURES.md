# Online Judge — Feature Plan (weeks 4–6)

The MVP in [PLAN.md](PLAN.md) takes weeks 1–3. This file covers what we build after that, with
**6 weeks in total**. Each feature lists who does what and the DB + API changes it needs, using the
same conventions as [MASTER_PLAN.md](MASTER_PLAN.md) (snake_case, UTC ISO timestamps, error
envelope, pagination envelope).

---

## 1. Overview

**Priority:**
- **P1** — must have, week 4.
- **P2** — should have, week 5.
- **P3** — stretch, week 6 only if the P1 + P2 checklist is green.

| ID | Feature | Why it's useful for a school OJ | Prio | A (backend) | B (judge) | C (frontend) |
|---|---|---|---|---|---|---|
| F1 | Contest leaderboard | Students see their ranking; teachers see the class at a glance | P1 | ● | | ● |
| F2 | Run with custom input | Test code before submitting, no wasted submissions | P1 | ● | ● | ● |
| F3 | Contest start/end time + countdown | Real exams and weekly deadlines | P1 | ● | | ● |
| F4 | More languages: C, Java | Common in HUST courses | P1 | ○ | ● | ○ |
| F5 | Export scores to CSV (Excel) | Teachers need grades in a spreadsheet | P1 | ● | | ● |
| F6 | Import students from CSV + private contests | Create a whole class at once; one contest per class | P1 | ● | | ● |
| F7 | Rejudge | Fix a wrong testcase, then re-score everyone | P1 | ● | | ● |
| F8 | Problem stats (solved / attempted) | Shows which problems are hard | P1 | ● | | ● |
| F9 | Float tolerance + custom checker | Problems with decimals or many correct answers | P2 | ○ | ● | ○ (B helps) |
| F10 | Show output diff on sample tests | Students see *why* they failed, without leaking hidden tests | P2 | ○ | ● | ● (B helps) |
| F11 | Plagiarism report | Teachers catch copied code | P2 | ○ | ● | ● (B helps) |
| F12 | Profile & personal stats | Progress tracking, nice for the demo | P2 | ● | | ● |
| F13 | Contest announcements | Teacher posts corrections/hints during a contest | P2 | ● | | ● |
| F14 | ENG / VI language switch | The screenshot UI has it; Vietnamese users | P2 | | | ● |
| F15 | Code draft autosave + load last submission | No lost code on page refresh | P2 | | | ● |
| F16 | Multiple judge workers | Handles a whole class submitting at the deadline | P2 | | ● | |
| F17 | Practice mode ("Learning") with tags | Problems outside contests, filtered by topic | P3 | ● | | ● |
| F18 | Live status via Server-Sent Events | Faster, nicer than polling | P3 | ● | | ● |
| F19 | Stronger sandbox (`isolate`) | Better security | P3 | | ● | |
| F20 | Dark mode | Polish | P3 | | | ● |

● = main work, ○ = small change.

**Frontend workload:** C has the most UI work. In week 5, B's judge tasks are lighter, so
**B builds the frontend pages for F9, F10 and F11** inside `frontend/`. Tell C before you start,
put the pages under `frontend/src/pages/admin/` or `frontend/src/features/<feature>/`, and use C's
API client and components.

---

## 2. Schedule (6 weeks)

| Week | Goal | A (Backend) | B (Judge) | C (Frontend) |
|---|---|---|---|---|
| 1 | Skeleton + basics | see PLAN.md | see PLAN.md | see PLAN.md |
| 2 | Walking skeleton | see PLAN.md | see PLAN.md | see PLAN.md |
| 3 | MVP complete | see PLAN.md | see PLAN.md | see PLAN.md |
| 4 | **P1 features** | F3, F1, F6, F5, F7, F8, run endpoints for F2 | F2 run worker, F4 C/Java | F3 countdown, F1 leaderboard, F2 run panel, F6/F5/F7 admin UI, F8 columns |
| 5 | **P2 features** + feature freeze on Friday | F12, F13, small parts of F9/F10/F11 | F9 checkers, F10 diffs, F11 plagiarism, F16 scaling, + their UI pages | F12 profile, F13 announcements, F14 i18n, F15 drafts |
| 6 | Hardening + demo | Bug fixes, tests, demo seed data | Security tests on sandbox, load test (30 submissions at once) | Bug fixes, responsive layout, E2E tests |
| 6 (if green) | P3 stretch | F17, F18 | F19 | F17, F18, F20 |

**Order within week 4:** do F3 first (it changes the contest object everyone uses), then F2
(it touches all three parts and takes the longest to integrate), then the rest.

---

## 3. Database changes (all done by A, as Alembic migrations)

One migration per feature, named `fNN_<name>` (e.g. `f02_test_runs`), so each can be merged alone.

```sql
-- F1 leaderboard
ALTER TABLE contests ADD COLUMN show_leaderboard BOOLEAN NOT NULL DEFAULT true;

-- F2 run with custom input
CREATE TABLE test_runs (
  id                 BIGSERIAL PRIMARY KEY,
  user_id            BIGINT NOT NULL REFERENCES users(id),
  problem_id         BIGINT NOT NULL REFERENCES problems(id),
  language           TEXT   NOT NULL,
  source_code        TEXT   NOT NULL,
  input              TEXT   NOT NULL,
  status             TEXT   NOT NULL DEFAULT 'PENDING'
                     CHECK (status IN ('PENDING','JUDGING','DONE','CE','SE')),
  verdict            TEXT   CHECK (verdict IN ('OK','TLE','MLE','RE')),   -- set when DONE
  stdout             TEXT,                                               -- cut to 64 KB
  stderr             TEXT,                                               -- cut to 8 KB
  compile_output     TEXT,
  time_ms            INT,
  memory_kb          INT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  judging_started_at TIMESTAMPTZ,
  finished_at        TIMESTAMPTZ
);
CREATE INDEX idx_test_runs_pending ON test_runs (id) WHERE status = 'PENDING';

-- F4 languages: widen the CHECK constraints
-- submissions.language and test_runs.language IN ('cpp17','python3','c11','java17')

-- F6 private contests
CREATE TABLE contest_participants (
  contest_id BIGINT NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
  user_id    BIGINT NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
  PRIMARY KEY (contest_id, user_id)
);

-- F9 checkers
ALTER TABLE problems ADD COLUMN checker_type  TEXT NOT NULL DEFAULT 'exact'
      CHECK (checker_type IN ('exact','float','custom'));
ALTER TABLE problems ADD COLUMN float_epsilon DOUBLE PRECISION NOT NULL DEFAULT 1e-6;
-- custom checker source lives at /data/problems/<problem_id>/checker.cpp

-- F10 sample output preview
ALTER TABLE submission_results ADD COLUMN output_preview TEXT;   -- only for sample tests, cut to 4 KB

-- F11 plagiarism
CREATE TABLE plagiarism_jobs (
  id          BIGSERIAL PRIMARY KEY,
  contest_id  BIGINT NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
  problem_id  BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
  status      TEXT   NOT NULL DEFAULT 'PENDING'
              CHECK (status IN ('PENDING','RUNNING','DONE','FAILED')),
  error       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at  TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);
CREATE TABLE plagiarism_pairs (
  job_id       BIGINT NOT NULL REFERENCES plagiarism_jobs(id) ON DELETE CASCADE,
  submission_a BIGINT NOT NULL REFERENCES submissions(id),
  submission_b BIGINT NOT NULL REFERENCES submissions(id),
  similarity   REAL   NOT NULL CHECK (similarity BETWEEN 0 AND 1),
  PRIMARY KEY (job_id, submission_a, submission_b)
);

-- F13 announcements
CREATE TABLE announcements (
  id         BIGSERIAL PRIMARY KEY,
  contest_id BIGINT NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
  title      TEXT   NOT NULL,
  body_md    TEXT   NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- F17 (stretch) practice mode
ALTER TABLE problems ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE problems ADD COLUMN is_practice BOOLEAN NOT NULL DEFAULT false;
```

### Column ownership additions (extends MASTER_PLAN §4.3)

| Table / column | Written by |
|---|---|
| `test_runs` insert (`status='PENDING'`) | **A** |
| `test_runs` PENDING → JUDGING → final + all result columns | **B** |
| `submission_results.output_preview` | **B** |
| `plagiarism_jobs` insert | **A** |
| `plagiarism_jobs` status/started/finished/error, `plagiarism_pairs` | **B** |
| **Rejudge (F7) — the only exception:** A may reset a *final* submission to `PENDING` (see F7) | **A** |
| `contest_participants`, `announcements`, new `problems`/`contests` columns | **A** |

### Judge job order (B)

Each loop, the judge claims at most one job, in this order:
**`test_runs` → `submissions` → `plagiarism_jobs`**.
Test runs go first because they are quick and a student is waiting at the screen. All three use
the same `FOR UPDATE SKIP LOCKED` pattern and the same stale-job recovery as MASTER_PLAN §7.1.

### New env vars (add to `.env.example`)

```dotenv
RUN_COOLDOWN_SECONDS=3          # backend: F2 rate limit
RUN_MAX_INPUT_BYTES=65536       # backend: F2
PLAGIARISM_MIN_SIMILARITY=0.5   # judge: F11, pairs below this are not stored
```

### New error codes (extends MASTER_PLAN §6.1)

| HTTP | `error.code` | When |
|---|---|---|
| 403 | `CONTEST_NOT_STARTED` | F3: student opens problems/submits before `start_time` |
| 403 | `CONTEST_ENDED` | F3: student submits after `end_time` |
| 403 | `LEADERBOARD_HIDDEN` | F1: `show_leaderboard=false` and user is not admin |

---

## 4. Features in detail

### F1 — Contest leaderboard (P1) · A, C

**Rules**
- For each user and problem: best score (same as "points earned").
- `total_score` = sum of best scores. `solved_count` = problems where score = max points.
- Sort by `total_score` DESC, then `last_improvement_at` ASC (the time of the submission that last
  raised the user's total; earlier is better), then `username`.
- Same total and same time → same rank. Compute on request (fine for a class-sized contest).
- Users with no submissions are not listed.

**API**
`GET /api/contests/{id}/leaderboard?page=1&size=50`
```json
{
  "problems": [ { "problem_id": 11, "code": "P_ADD_SUB_MUL_DIV", "max_points": 100 } ],
  "items": [
    {
      "rank": 1,
      "user": { "id": 2, "username": "student1", "full_name": "Nguyen Van A" },
      "total_score": 5170, "solved_count": 53,
      "last_improvement_at": "2026-11-20T09:40:00Z",
      "cells": [ { "problem_id": 11, "score": 100, "attempts": 2 } ]
    }
  ],
  "page": 1, "size": 50, "total": 120
}
```
`cells` uses the same order as `problems`; problems with no attempts have `score: 0, attempts: 0`.

**Frontend:** third tab "Leaderboard" on the contest page. Highlight the current user's row.
Cell colors: green = full score, yellow = partial, red = attempted with 0 points, empty = not attempted.

---

### F2 — Run with custom input (P1) · A, B, C

**Rules:** a test run does **not** count as a submission and gives no points. It runs the code
once on the given input with the problem's time/memory limits and returns stdout/stderr. There
is no expected output and no comparison.

**API**
- `POST /api/contests/{cid}/problems/{pid}/run`
  `{ "language": "cpp17", "source_code": "...", "input": "3 5\n" }` → 201 `{ "run_id": 77, "status": "PENDING" }`
  Errors: 413 if input > `RUN_MAX_INPUT_BYTES`, 429 if within `RUN_COOLDOWN_SECONDS`, F3 errors.
- `GET /api/runs/{id}` (owner or admin only):
```json
{
  "id": 77, "status": "DONE", "verdict": "OK",
  "stdout": "8\n-2\n15\n0\n", "stderr": "", "compile_output": null,
  "time_ms": 4, "memory_kb": 3300, "created_at": "2026-11-20T09:41:00Z"
}
```

**Judge (B):** reuse the compile + run-one-test code from submissions. Status `CE` if compile
fails, `SE` on judge errors, else `DONE` with `verdict` OK/TLE/MLE/RE.
**Backend (A):** on startup, delete test runs older than 24 h.
**Frontend (C):** panel under the editor with an "Input" box (pre-filled with the first sample),
a "Run" button, and an "Output" box. Poll like submissions. Keyboard shortcut Ctrl+' for Run.

---

### F3 — Contest time window + countdown (P1) · A, C

**Rules (students only; admins are never blocked)**

| Contest state | See in list | See problems | Submit / run |
|---|---|---|---|
| `upcoming` (now < start_time) | yes | no → `CONTEST_NOT_STARTED` | no |
| `running` | yes | yes | yes |
| `ended` (now > end_time) | yes | yes | no → `CONTEST_ENDED` |

`start_time` / `end_time` = `null` means no limit on that side.

**API:** every contest object (list + detail) gets two new fields:
`"status": "upcoming" | "running" | "ended"` and `"server_time": "2026-11-20T09:49:00Z"`.

**Frontend:** a status chip in the contest list. On the contest page, a countdown
("Starts in 02:13:45" / "Ends in 00:45:10"), computed from `server_time` so a wrong laptop clock
doesn't matter. Turns red in the last 10 minutes. Submit/Run are disabled when ended.

---

### F4 — C and Java (P1) · B (+ small A, C)

Add to `judge/languages.yaml`:

```yaml
c11:
  source_file: main.c
  compile: ["gcc", "-O2", "-std=c11", "-pipe", "-o", "main", "main.c", "-lm"]
  run: ["./main"]
  time_multiplier: 1.0
java17:
  source_file: Main.java          # students must name the class Main
  compile: ["javac", "-encoding", "UTF-8", "Main.java"]
  run: ["java", "-Xmx{memory_limit_mb}m", "-Xss64m", "-cp", ".", "Main"]
  time_multiplier: 2.0            # JVM startup is slow
  memory_by_jvm: true             # don't use RLIMIT_AS (breaks the JVM); -Xmx sets the limit
```

- **Every language** gets `time_multiplier` (default 1.0). The effective limit is `time_limit_ms × time_multiplier`.
- B installs `gcc` and `openjdk-17-jdk-headless` in the judge Dockerfile and adds C and Java
  versions of every program in `judge/samples/`.
- A widens the `CHECK` constraints and adds `c11`, `java17` to `languages` in the problem detail.
- C adds them to the dropdown and the Monaco language mapping. Default starter code for Java
  shows `public class Main`.

---

### F5 — Export scores to CSV (P1) · A, C

`GET /api/admin/contests/{id}/export.csv` → `Content-Type: text/csv`,
`Content-Disposition: attachment; filename="<contest_code>_scores.csv"`.

```
username,full_name,P_ADD_SUB_MUL_DIV,P_BASIC_QUERIES,...,total,solved
student1,Nguyen Van A,100,100,...,5170,53
```

- Encoding **UTF-8 with BOM** so Excel shows Vietnamese names correctly.
- One row per participant (or per user who submitted, for public contests), sorted by username.
- Frontend: "Export CSV" button for admins on the contest page.

---

### F6 — Import students + private contests (P1) · A, C

**Rules**
- `is_public = true` → every logged-in user sees it (MVP behavior).
- `is_public = false` → only users in `contest_participants` (and admins) see it; others get 404.

**API**
- `POST /api/admin/users/import` (multipart): `file` = CSV with header `username,full_name,password`,
  optional field `contest_id` adds all imported users (new and existing) as participants.
```json
{ "created": 38, "existing": 2, "added_to_contest": 40,
  "errors": [ { "line": 7, "reason": "username is empty" } ] }
```
  Validates every row first. If any row has an error, nothing is saved (all or nothing).
- `GET /api/admin/users?search=&page=&size=` → paginated `{id, username, full_name, role, created_at}`.
- `POST /api/admin/contests/{id}/participants` `{ "user_ids": [2,3] }` / `DELETE .../participants/{user_id}`.
- `GET /api/admin/contests/{id}/participants?page=&size=`.
- `POST /api/auth/change-password` `{ "old_password": "...", "new_password": "..." }` → 204.
  New password at least 6 characters. Imported students should change their password.

**Frontend:** Admin → Users page (table + "Import CSV" with a result summary showing errors by line),
a Participants tab in contest admin, and a "Change password" item in the avatar menu.

---

### F7 — Rejudge (P1) · A, C

`POST /api/admin/submissions/{id}/rejudge` → 202
`POST /api/admin/contests/{cid}/problems/{pid}/rejudge` → 202 `{ "count": 87 }`

A does, **in one transaction**: delete the submission's `submission_results`; set
`status='PENDING'`, `score=0`, `tests_passed=0`, `tests_total=0`, `time_ms/memory_kb/compile_output/judging_started_at/judged_at = NULL`.
Skip submissions that are currently `PENDING`/`JUDGING`. The judge needs no changes.

**Frontend:** "Rejudge" button on the submission detail page (admin) and "Rejudge all" on the
admin problem view, with a confirm dialog that shows the count.

---

### F8 — Problem stats (P1) · A, C

Add to each item of `GET /api/contests/{id}/problems`:
`"solved_count": 41` (users with full score) and `"attempted_count": 52` (users with ≥ 1 submission).

**Frontend:** a "Solved" column showing `41 / 52`, sortable on the client.

---

### F9 — Float tolerance + custom checker (P2) · B (+ A, B does UI)

| `checker_type` | Compare rule |
|---|---|
| `exact` | MVP rule (MASTER_PLAN §7.3) |
| `float` | Split both outputs into tokens. Same token count. Number tokens match if `abs(a-b) <= eps` or `abs(a-b) <= eps*abs(b)`. Other tokens must match exactly. |
| `custom` | Run the checker: `./checker <input_file> <user_output_file> <expected_output_file>`. Exit code 0 = AC, 1 = WA, 2 = WA (presentation), anything else = `SE`. Compatible with [testlib](https://github.com/MikeMirzayanov/testlib) checkers. |

- `POST /api/admin/problems/{id}/checker` (multipart `file` = `checker.cpp`) — A saves it to
  `/data/problems/<id>/checker.cpp`. B compiles it on first use and caches the binary in the
  judge container by `(problem_id, file modified time)`. B adds `testlib.h` to the judge image.
- The checker runs with a 10 s time limit inside the same sandbox as user code.
- Problem create/update accepts `checker_type`, `float_epsilon`. Problem detail returns them.
- **UI (B):** checker fields on the admin problem form + checker upload.

---

### F10 — Output diff on sample tests (P2) · B (+ A, B/C do UI)

- For tests with `is_sample = true`, B saves the first 4 KB of the user's output in
  `submission_results.output_preview`. Hidden tests are never shown.
- `GET /api/submissions/{id}` → each item in `results` gets:
```json
{ "order_index": 1, "verdict": "WA", "time_ms": 3, "memory_kb": 3300,
  "is_sample": true,
  "sample": { "input": "3 5\n", "expected": "8\n-2\n15\n0\n", "output": "8\n2\n15\n0\n" } }
```
  `sample` is `null` for hidden tests.
- **UI (B):** a side-by-side diff of expected vs output with differing lines highlighted
  (use a small library like `diff`).

---

### F11 — Plagiarism report (P2) · B (+ A, B does UI)

**Method (B):** for each user, take their **best-scoring** submission (newest on a tie) for the
problem. Compare every pair of users with the same language. Try [Dolos](https://dolos.ugent.be/)
(open source, supports C/C++/Python/Java, can run as a CLI) first. If it doesn't fit, write your own:
1. Tokenize; remove comments and whitespace; replace identifiers with `ID` and literals with `LIT`.
2. Fingerprints with *k*-grams + winnowing (the MOSS algorithm).
3. `similarity = |A ∩ B| / min(|A|, |B|)`.

Store pairs with `similarity >= PLAGIARISM_MIN_SIMILARITY`.

**API**
- `POST /api/admin/contests/{cid}/problems/{pid}/plagiarism` → 202 `{ "job_id": 5 }`
- `GET /api/admin/plagiarism/{job_id}`:
```json
{
  "id": 5, "status": "DONE", "error": null, "finished_at": "2026-11-20T10:00:00Z",
  "pairs": [
    { "similarity": 0.93,
      "a": { "submission_id": 120, "username": "student7" },
      "b": { "submission_id": 131, "username": "student12" } }
  ]
}
```
  Pairs sorted by similarity, highest first.

**UI (B):** admin page with a "Check plagiarism" button per problem, a results table with
similarity bars, and a side-by-side code view (two read-only Monaco editors) for each pair.
**Wording in the UI:** "high similarity", not "cheating" — a teacher makes the final decision.

---

### F12 — Profile & personal stats (P2) · A, C

`GET /api/users/me/stats`:
```json
{
  "solved_count": 53, "submission_count": 140,
  "by_verdict": { "AC": 80, "WA": 30, "TLE": 10, "RE": 8, "CE": 7, "PARTIAL": 5 },
  "by_language": { "cpp17": 120, "python3": 20 },
  "activity": [ { "date": "2026-11-19", "count": 6 } ]
}
```
`activity` covers the last 90 days, days with 0 submissions left out, dates in **Asia/Ho_Chi_Minh**.

**Frontend:** a profile page with stat tiles, a verdict bar chart, and an activity heatmap
(GitHub-style), plus the "Change password" form from F6.

---

### F13 — Announcements (P2) · A, C

- `GET /api/contests/{id}/announcements` → `[{ id, title, body_md, created_at }]`, newest first.
- `POST /api/admin/contests/{id}/announcements` `{ title, body_md }` → 201.
- `DELETE /api/admin/announcements/{id}` → 204.

**Frontend:** poll every 60 s on the contest page. A new announcement shows a toast and a badge;
there is a list in a side panel. Markdown is rendered with the same safe renderer as statements.

---

### F14 — ENG / VI switch (P2) · C

`react-i18next`, files `frontend/src/i18n/en.json` and `vi.json`. The choice is saved in localStorage.
**The API stays English:** verdict codes, levels and error codes are translated in the frontend only
(e.g. `WA` → "Sai kết quả"). Problem statements are not translated.

---

### F15 — Draft autosave + load last submission (P2) · C

- Save editor content to localStorage every 2 s under key `draft:<contest_id>:<problem_id>:<language>`.
- When the problem page opens, restore the draft for the selected language.
- "Load last submission" button: fetches the latest submission via the existing submissions API.
- No backend change.

---

### F16 — Multiple judge workers (P2) · B

Claiming is already safe for several workers (`SKIP LOCKED`). B checks that
`docker compose up --scale judge=3` works (no fixed container name, temp dirs are unique per job),
and runs a load test: 30 submissions at once, all judged correctly, none judged twice.

---

### P3 stretch (week 6, only if everything above is done)

- **F17 Practice mode:** problems with `is_practice=true` show up in a "Learning" page with tag and
  level filters (`GET /api/practice/problems?tag=&level=&search=`). Practice submissions use a
  built-in hidden contest `code='practice'`, so no schema change is needed for submissions.
- **F18 Live status (SSE):** `GET /api/submissions/{id}/events` streams status changes. Keep
  polling as the fallback.
- **F19 `isolate` sandbox:** run each test with [isolate](https://github.com/ioi/isolate)
  (cgroups-based, used by IOI) instead of plain `setrlimit`.
- **F20 Dark mode:** MUI theme toggle, saved in localStorage.

---

## 5. Feature acceptance checklist (end of week 5)

Run together with MASTER_PLAN §12 on a fresh clone:

- [ ] F1 Leaderboard ranks correctly, including ties; hidden when `show_leaderboard=false`
- [ ] F2 Run shows stdout for a correct program, TLE for an infinite loop, compile errors for CE; gives no points
- [ ] F3 Student can't see problems before start or submit after end; countdown is right with a wrong PC clock
- [ ] F4 C and Java samples give all verdicts correctly; Java TLE uses ×2 time
- [ ] F5 CSV opens in Excel with correct Vietnamese names and totals
- [ ] F6 Importing a 40-row CSV creates the users; one bad row → nothing created and the line number shown; private contest hidden from non-participants
- [ ] F7 Fix a testcase → "Rejudge all" → scores and leaderboard update
- [ ] F8 Solved/attempted counts match the database
- [ ] F9 A float problem accepts `0.3333334` for `0.333333`; a testlib checker works
- [ ] F10 Sample diff shown on WA; hidden tests show no data
- [ ] F11 Two copied solutions with renamed variables get ≥ 0.8 similarity; unrelated ones are not listed
- [ ] F12 Profile numbers match the submissions list
- [ ] F13 New announcement appears within 60 s without refresh
- [ ] F14 Every page switches between ENG/VI with no missing keys
- [ ] F15 Refresh the page → code is still there
- [ ] F16 30 submissions at once with 3 workers → all judged once, correct verdicts
