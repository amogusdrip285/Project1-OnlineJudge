"""Regression tests for issues found in the week-2 code and security reviews."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Contest, Problem, Submission
from app.services.submissions import _check_cooldown
from scripts import fake_judge, seed
from tests.conftest import TEST_JWT_SECRET
from tests.factories import (
    FAST_BCRYPT_ROUNDS,
    attach,
    auth_header,
    make_contest,
    make_problem,
    make_submission,
    make_testcase,
    make_user,
)

REPO_SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed" / "problems"
HUGE = "99999999999999999999"


@pytest.fixture
def headers(db: Session) -> dict[str, str]:
    return auth_header(make_user(db), TEST_JWT_SECRET)


@pytest.fixture
def contest_problem(db: Session) -> tuple[Contest, Problem]:
    contest = make_contest(db)
    problem = make_problem(db)
    attach(db, contest, problem)
    return contest, problem


# --- bad input is a 400, never a 500 ---


@pytest.mark.parametrize(
    "path",
    [
        f"/api/contests/{HUGE}",
        f"/api/contests/{HUGE}/problems",
        f"/api/contests/1/problems/{HUGE}",
        f"/api/submissions/{HUGE}",
        f"/api/contests/1/submissions?problem_id={HUGE}",
        f"/api/contests/1/submissions?user_id={HUGE}",
        f"/api/contests?page={HUGE}",
        "/api/contests/0",
        "/api/contests/1/problems?search=a%00b",
    ],
)
def test_out_of_range_or_nul_input_is_400(api: TestClient, headers: dict, path: str) -> None:
    response = api.get(path, headers=headers)

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_nul_byte_in_source_is_400(
    api: TestClient, headers: dict, contest_problem: tuple[Contest, Problem]
) -> None:
    contest, problem = contest_problem

    response = api.post(
        f"/api/contests/{contest.id}/problems/{problem.id}/submit",
        json={"language": "cpp17", "source_code": "int main(){}\u0000"},
        headers=headers,
    )

    assert response.status_code == 400


def test_db_data_error_becomes_400(app, client: TestClient) -> None:
    from sqlalchemy.exc import DataError

    @app.get("/api/_test/data-error")
    def raise_data_error() -> None:
        raise DataError("SELECT 1", {}, Exception("value out of range"))

    response = client.get("/api/_test/data-error")

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input value",
    }


# --- cooldown row lock really blocks a parallel request ---


def test_cooldown_locks_the_user_row(db_engine: Engine) -> None:
    with db_engine.begin() as setup:
        user_id = setup.execute(
            text(
                "INSERT INTO users (username, password_hash, full_name, role) "
                "VALUES ('lock_test_user', 'x', 'Lock Test', 'student') RETURNING id"
            )
        ).scalar_one()
    try:
        with Session(db_engine) as first, db_engine.connect() as second:
            _check_cooldown(first, user_id, cooldown_seconds=5)  # holds the row lock
            second.execute(text("SET lock_timeout = '200ms'"))
            with pytest.raises(OperationalError, match="lock"):
                second.execute(
                    text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": user_id}
                )
            first.rollback()
    finally:
        with db_engine.begin() as cleanup:
            cleanup.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


# --- fake judge ---


def test_fake_judge_lost_job_rolls_back_results(db: Session) -> None:
    contest = make_contest(db)
    problem = make_problem(db)
    attach(db, contest, problem)
    make_testcase(db, problem, 1)
    submission = make_submission(db, make_user(db), contest, problem)  # PENDING, not JUDGING
    connection = db.connection()

    with pytest.raises(fake_judge.LostJobError):
        fake_judge.finish_as_accepted(connection, submission.id, problem.id, 100)


def test_fake_judge_resets_stale_jobs(db: Session) -> None:
    contest = make_contest(db)
    problem = make_problem(db)
    attach(db, contest, problem)
    user = make_user(db)
    stale = make_submission(
        db,
        user,
        contest,
        problem,
        status="JUDGING",
        judging_started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    fresh = make_submission(
        db, user, contest, problem, status="JUDGING", judging_started_at=datetime.now(UTC)
    )

    fake_judge.reset_stale(db.connection(), seconds=120)
    db.expire_all()

    assert db.get_one(Submission, stale.id).status == "PENDING"
    assert db.get_one(Submission, fresh.id).status == "JUDGING"


# --- seed ---


def test_seed_keeps_admin_edits(db: Session, tmp_path: Path) -> None:
    seed.run_seed(db, REPO_SEED_DIR, tmp_path, bcrypt_rounds=FAST_BCRYPT_ROUNDS)
    problem = db.scalar(select(Problem).where(Problem.code == "P_ADD_SUB_MUL_DIV"))
    contest = db.scalar(select(Contest).where(Contest.code == seed.CONTEST_CODE))
    problem.title = "Edited by admin"
    contest.is_public = False
    db.flush()

    seed.run_seed(db, REPO_SEED_DIR, tmp_path, bcrypt_rounds=FAST_BCRYPT_ROUNDS)
    db.expire_all()

    assert db.get_one(Problem, problem.id).title == "Edited by admin"
    assert db.get_one(Contest, contest.id).is_public is False


def test_seed_refuses_production(monkeypatch: pytest.MonkeyPatch) -> None:
    production = Settings(env="production", jwt_secret="a-real-secret-that-is-long-enough-1234")
    monkeypatch.setattr(seed, "get_settings", lambda: production)

    with pytest.raises(SystemExit, match="production"):
        seed.main()
