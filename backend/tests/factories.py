"""Helpers that insert rows for tests. Every helper flushes so ids are available."""

from itertools import count

from sqlalchemy.orm import Session

from app.models import (
    Contest,
    ContestProblem,
    Problem,
    Submission,
    SubmissionResult,
    Testcase,
    User,
)
from app.security import create_access_token, hash_password

FAST_BCRYPT_ROUNDS = 4  # the minimum; keeps tests fast
DEFAULT_PASSWORD = "secret123"

_ids = count(1)


def _unique(prefix: str) -> str:
    return f"{prefix}_{next(_ids)}"


def make_user(
    db: Session,
    *,
    username: str | None = None,
    password: str = DEFAULT_PASSWORD,
    role: str = "student",
    full_name: str = "Test User",
) -> User:
    user = User(
        username=username or _unique("user"),
        password_hash=hash_password(password, rounds=FAST_BCRYPT_ROUNDS),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def auth_header(user: User, secret: str) -> dict[str, str]:
    token = create_access_token(user.id, user.role, secret, expire_minutes=60)
    return {"Authorization": f"Bearer {token}"}


def make_contest(db: Session, *, is_public: bool = True, **fields) -> Contest:
    contest = Contest(
        code=fields.pop("code", None) or _unique("contest"),
        title=fields.pop("title", "Test contest"),
        is_public=is_public,
        **fields,
    )
    db.add(contest)
    db.flush()
    return contest


def make_problem(db: Session, **fields) -> Problem:
    problem = Problem(
        code=fields.pop("code", None) or _unique("P"),
        title=fields.pop("title", "Test problem"),
        statement_md=fields.pop("statement_md", "Statement"),
        level=fields.pop("level", "easy"),
        **fields,
    )
    db.add(problem)
    db.flush()
    return problem


def attach(
    db: Session, contest: Contest, problem: Problem, *, max_points: int = 100, order_index: int = 1
) -> ContestProblem:
    link = ContestProblem(
        contest_id=contest.id, problem_id=problem.id, max_points=max_points, order_index=order_index
    )
    db.add(link)
    db.flush()
    return link


def make_testcase(
    db: Session, problem: Problem, order_index: int, *, is_sample: bool = False
) -> Testcase:
    testcase = Testcase(
        problem_id=problem.id,
        order_index=order_index,
        input_path=f"{problem.id}/tests/{order_index}.in",
        output_path=f"{problem.id}/tests/{order_index}.out",
        is_sample=is_sample,
    )
    db.add(testcase)
    db.flush()
    return testcase


def make_submission(
    db: Session,
    user: User,
    contest: Contest,
    problem: Problem,
    *,
    status: str = "PENDING",
    score: int = 0,
    max_points: int = 100,
    language: str = "cpp17",
    **fields,
) -> Submission:
    submission = Submission(
        user_id=user.id,
        contest_id=contest.id,
        problem_id=problem.id,
        language=language,
        source_code=fields.pop("source_code", "int main() {}"),
        max_points=max_points,
        status=status,
        score=score,
        **fields,
    )
    db.add(submission)
    db.flush()
    return submission


def make_result(
    db: Session, submission: Submission, testcase: Testcase, verdict: str = "AC"
) -> SubmissionResult:
    result = SubmissionResult(
        submission_id=submission.id,
        testcase_id=testcase.id,
        verdict=verdict,
        time_ms=3,
        memory_kb=3300,
    )
    db.add(result)
    db.flush()
    return result
