"""scripts/seed.py and scripts/fake_judge.py against the test DB."""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.models import Contest, ContestProblem, Problem, Submission, User
from scripts import fake_judge
from scripts.seed import CONTEST_CODE, run_seed
from tests.factories import (
    FAST_BCRYPT_ROUNDS,
    attach,
    make_contest,
    make_problem,
    make_submission,
    make_testcase,
    make_user,
)

REPO_SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed" / "problems"
SEED_PROBLEM_CODES = {
    "P_ADD_SUB_MUL_DIV",
    "P_HHMMSS_TO_SECONDS",
    "P_UPPERCASE_TEXT",
    "P_SUM_OF_ARRAY",
    "P_MAX_OF_THREE",
}


def _counts(db: Session) -> tuple[int, ...]:
    return tuple(
        db.scalar(select(func.count()).select_from(model))
        for model in (User, Contest, Problem, ContestProblem, models.Testcase, Submission)
    )


def _seed(db: Session, problems_dir: Path):
    return run_seed(db, REPO_SEED_DIR, problems_dir, bcrypt_rounds=FAST_BCRYPT_ROUNDS)


def test_seed_loads_users_contest_problems_and_files(db: Session, tmp_path: Path) -> None:
    summary = _seed(db, tmp_path)

    contest = db.scalar(select(Contest).where(Contest.code == CONTEST_CODE))
    codes = set(
        db.scalars(
            select(Problem.code)
            .join(ContestProblem, ContestProblem.problem_id == Problem.id)
            .where(ContestProblem.contest_id == contest.id)
        )
    )
    total_points = db.scalar(
        select(func.sum(ContestProblem.max_points)).where(ContestProblem.contest_id == contest.id)
    )
    add = db.scalar(select(Problem).where(Problem.code == "P_ADD_SUB_MUL_DIV"))
    first_input = tmp_path / f"{add.id}" / "tests" / "1.in"

    assert summary.problems == 5
    assert summary.demo_submissions_created == 3
    assert codes == SEED_PROBLEM_CODES
    assert total_points == 560
    assert first_input.read_bytes() == b"3 5\n"
    assert b"\r" not in (tmp_path / f"{add.id}" / "tests" / "1.out").read_bytes()


def test_seed_is_idempotent(db: Session, tmp_path: Path) -> None:
    _seed(db, tmp_path)
    before = _counts(db)

    second = _seed(db, tmp_path)

    assert _counts(db) == before
    assert second.users_created == 0
    assert second.testcase_files_written == 0
    assert second.demo_submissions_created == 0


def test_seed_rewrites_missing_testcase_files(db: Session, tmp_path: Path) -> None:
    _seed(db, tmp_path)
    victim = next(tmp_path.glob("*/tests/1.in"))
    victim.unlink()

    summary = _seed(db, tmp_path)

    assert summary.testcase_files_written == 1
    assert victim.is_file()


def test_seed_demo_submissions_for_student2(db: Session, tmp_path: Path) -> None:
    _seed(db, tmp_path)
    student2 = db.scalar(select(User).where(User.username == "student2"))
    statuses = {
        code: (status, score)
        for code, status, score in db.execute(
            select(Problem.code, Submission.status, Submission.score)
            .join(Problem, Problem.id == Submission.problem_id)
            .where(Submission.user_id == student2.id)
        )
    }

    assert statuses == {
        "P_MAX_OF_THREE": ("AC", 100),
        "P_ADD_SUB_MUL_DIV": ("PARTIAL", 70),
        "P_HHMMSS_TO_SECONDS": ("CE", 0),
    }


def test_seed_fails_clearly_without_seed_dir(db: Session, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        run_seed(db, tmp_path / "missing", tmp_path)


def test_fake_judge_marks_pending_as_ac_with_results(db: Session) -> None:
    contest = make_contest(db)
    problem = make_problem(db)
    attach(db, contest, problem, max_points=100)
    for order in (1, 2, 3):
        make_testcase(db, problem, order)
    submission = make_submission(db, make_user(db), contest, problem)
    connection = db.connection()

    job = fake_judge.claim(connection)
    status = fake_judge.finish_as_accepted(connection, *job)
    db.refresh(submission)

    assert job == (submission.id, problem.id, 100)
    assert status == "AC"
    assert (submission.status, submission.score, submission.tests_passed) == ("AC", 100, 3)
    assert submission.judged_at is not None


def test_fake_judge_gives_se_without_testcases(db: Session) -> None:
    contest = make_contest(db)
    problem = make_problem(db)
    attach(db, contest, problem)
    make_submission(db, make_user(db), contest, problem)
    connection = db.connection()

    status = fake_judge.finish_as_accepted(connection, *fake_judge.claim(connection))

    assert status == "SE"


def test_fake_judge_claim_returns_none_when_queue_empty(db: Session) -> None:
    connection = db.connection()
    while fake_judge.claim(connection) is not None:  # drain leftovers from manual runs
        pass

    assert fake_judge.claim(connection) is None
