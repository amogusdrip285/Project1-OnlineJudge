# Online Judge

A small online judge for a school project: contests, problems, code submissions, automatic
judging with partial scores.

## Run it

Needs Docker Desktop (Windows: WSL 2 backend).

```bash
cp .env.example .env
docker compose up --build
```

| What | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API health | http://localhost:8000/api/health |
| API docs (Swagger) | http://localhost:8000/docs |
| Postgres | `127.0.0.1:5432` (not `localhost`: on Windows it tries IPv6 first and hangs), user/db `oj`, password in `.env` |

Stop with `Ctrl+C`; wipe the database **and** the testcase volume with `docker compose down -v`.

### Demo data

With `SEED_ON_START=true` (the default in `.env.example`) the backend loads demo data on every
start; it is safe to run again and never deletes submissions.

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | admin |
| `student1` | `123456` | student — no submissions |
| `student2` | `123456` | student — has an AC, a PARTIAL (70/100) and a CE submission |
| `student3` | `123456` | student |

Contest `project120261` has the 5 problems in [data/seed/problems/](data/seed/problems/) (560
points in total). Each problem folder has `problem.yaml`, `statement.md`, `tests/` and reference
`solutions/`.

### Without the real judge

`scripts/fake_judge.py` marks every PENDING submission as AC. Use it only while the judge
container is stopped:

```bash
docker compose stop judge
docker compose exec backend python -m scripts.fake_judge
```

### Smoke test

From the repo root, with the stack running (and a judge or the fake judge):

```bash
python scripts/smoke_test.py   # login -> submit A+B -> AC -> points updated
```

## Project layout

| Folder | Owner | What |
|---|---|---|
| `backend/` | A | FastAPI REST API, DB models, Alembic migrations |
| `judge/` | B | Judge worker (compile, run, verdicts) — *placeholder for now* |
| `frontend/` | C | React app — *placeholder for now* |
| `data/seed/problems/` | all | Sample problems + testcases committed to git |
| `docs/` | all | Plans and specs — start with [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md) |

## Backend development

```bash
cd backend
uv sync                      # install deps into backend/.venv
uv run pytest                # tests (DB tests skip unless TEST_DATABASE_URL is set)
uv run ruff check . && uv run ruff format .
```

DB tests against the compose database:

```bash
docker compose up -d db
docker compose exec db createdb -U oj oj_test
TEST_DATABASE_URL=postgresql://oj:change-me@127.0.0.1:5432/oj_test uv run pytest
```

New migration (after changing `app/models/`):

```bash
uv run alembic revision -m "f01 leaderboard"   # then write upgrade()/downgrade()
```

## Workflow

Branch per feature (`backend/auth`, `judge/limits`, `frontend/problem-page`), open a PR, merge
yourself when CI is green, and post the link in the group chat. Details:
[docs/MASTER_PLAN.md §10](docs/MASTER_PLAN.md).

## Docs

- [docs/PLAN.md](docs/PLAN.md) — MVP scope and work split
- [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md) — DB, API and judge specs, conventions, schedule
- [docs/FEATURES.md](docs/FEATURES.md) — features for weeks 4–6
- [docs/PERSON_A.md](docs/PERSON_A.md) — backend plan
- [docs/WEEK2_PLAN.md](docs/WEEK2_PLAN.md) — week 2 (walking skeleton) plan for A, B, C
- [docs/reports/](docs/reports/) — weekly progress reports
