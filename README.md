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
| Postgres | `localhost:5432`, user/db `oj` (password in `.env`) |

Stop with `Ctrl+C`; wipe the database with `docker compose down -v`.

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
TEST_DATABASE_URL=postgresql://oj:change-me@localhost:5432/oj_test uv run pytest
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
