"""Load demo data: users, contest `project120261`, 5 problems with testcases (WEEK2_PLAN §2.3).

Idempotent: safe to run on every start (`SEED_ON_START=true`). It only creates what is missing
and never changes existing rows, so admin edits survive restarts: users keep their password,
existing contests/problems/testcases are untouched, missing testcase files are restored, and
demo submissions are added only if `student2` has none. Refused when ENV=production.

    python -m scripts.seed            # inside the backend container
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import LEVELS
from app.db import SessionLocal
from app.models import (
    Contest,
    ContestProblem,
    Problem,
    Submission,
    SubmissionResult,
    Testcase,
    User,
)
from app.security import BCRYPT_ROUNDS, hash_password

logger = logging.getLogger("seed")

CONTEST_CODE = "project120261"
DEMO_STUDENT = "student2"
SEED_LOCK_KEY = 20261  # arbitrary, unique to the seed
REQUIRED_PROBLEM_FIELDS = (
    "code",
    "title",
    "level",
    "time_limit_ms",
    "memory_limit_mb",
    "max_points",
    "order_index",
    "sample_count",
)


@dataclass(frozen=True)
class SeedUser:
    username: str
    password: str
    full_name: str
    role: str


SEED_USERS = (
    SeedUser("admin", "admin123", "Admin", "admin"),
    SeedUser("student1", "123456", "Nguyen Van A", "student"),
    SeedUser("student2", "123456", "Tran Thi B", "student"),
    SeedUser("student3", "123456", "Le Van C", "student"),
)


@dataclass(frozen=True)
class SeedSummary:
    users_created: int
    problems: int
    testcase_files_written: int
    demo_submissions_created: int


def _ensure_users(db: Session, bcrypt_rounds: int) -> tuple[int, dict[str, User]]:
    created = 0
    users: dict[str, User] = {}
    for seed_user in SEED_USERS:
        user = db.scalar(select(User).where(User.username == seed_user.username))
        if user is None:
            user = User(
                username=seed_user.username,
                password_hash=hash_password(seed_user.password, rounds=bcrypt_rounds),
                full_name=seed_user.full_name,
                role=seed_user.role,
            )
            db.add(user)
            created += 1
        users[seed_user.username] = user
    db.flush()
    return created, users


def _ensure_contest(db: Session) -> Contest:
    contest = db.scalar(select(Contest).where(Contest.code == CONTEST_CODE))
    if contest is None:
        contest = Contest(
            code=CONTEST_CODE,
            title="Project 1 - 2026.1",
            description="Weekly exercises",
            start_time=datetime(2026, 9, 1, tzinfo=UTC),
            end_time=datetime(2027, 1, 15, tzinfo=UTC),
            is_public=True,
        )
        db.add(contest)
        db.flush()
    return contest


def _read_problem_meta(folder: Path) -> dict:
    meta = yaml.safe_load((folder / "problem.yaml").read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ValueError(f"{folder}/problem.yaml must be a mapping")
    missing = [field for field in REQUIRED_PROBLEM_FIELDS if field not in meta]
    if missing:
        raise ValueError(f"{folder}/problem.yaml is missing {missing}")
    if meta["level"] not in LEVELS:
        raise ValueError(f"{folder}/problem.yaml: bad level {meta['level']!r}")
    if meta["code"] != folder.name:
        raise ValueError(f"{folder}: folder name must equal code {meta['code']!r}")
    return meta


def _count_tests(folder: Path) -> int:
    """Number of test pairs; they must be 1..n with no gaps (MASTER_PLAN §5)."""
    tests_dir = folder / "tests"
    count = len(list(tests_dir.glob("*.in")))
    for n in range(1, count + 1):
        if not (tests_dir / f"{n}.in").is_file() or not (tests_dir / f"{n}.out").is_file():
            raise ValueError(f"{tests_dir}: test pair {n} is missing")
    return count


def _copy_lf(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))


def _create_problem(db: Session, contest: Contest, folder: Path, meta: dict) -> Problem:
    problem = Problem(
        code=meta["code"],
        title=meta["title"],
        statement_md=(folder / "statement.md").read_text(encoding="utf-8"),
        level=meta["level"],
        time_limit_ms=int(meta["time_limit_ms"]),
        memory_limit_mb=int(meta["memory_limit_mb"]),
    )
    db.add(problem)
    db.flush()
    db.add(
        ContestProblem(
            contest_id=contest.id,
            problem_id=problem.id,
            max_points=int(meta["max_points"]),
            order_index=int(meta["order_index"]),
        )
    )
    for n in range(1, _count_tests(folder) + 1):
        db.add(
            Testcase(
                problem_id=problem.id,
                order_index=n,
                input_path=f"{problem.id}/tests/{n}.in",
                output_path=f"{problem.id}/tests/{n}.out",
                is_sample=n <= int(meta["sample_count"]),
            )
        )
    db.flush()
    return problem


def _ensure_problem(db: Session, contest: Contest, folder: Path, problems_dir: Path) -> int:
    """Create the problem (+ contest link + testcases) if it doesn't exist yet.

    An existing problem is left as it is, so admin edits survive restarts; only its missing
    testcase files are restored from the seed folder. Returns testcase files written.
    """
    meta = _read_problem_meta(folder)
    problem = db.scalar(select(Problem).where(Problem.code == meta["code"]))
    is_new = problem is None
    if problem is None:
        problem = _create_problem(db, contest, folder, meta)

    written = 0
    testcases = db.scalars(select(Testcase).where(Testcase.problem_id == problem.id)).all()
    for testcase in testcases:
        for ext, rel_path in (("in", testcase.input_path), ("out", testcase.output_path)):
            source = folder / "tests" / f"{testcase.order_index}.{ext}"
            target = problems_dir / rel_path
            # New problems always overwrite: a file left over from an older database may differ.
            if source.is_file() and (is_new or not target.is_file()):
                _copy_lf(source, target)
                written += 1
    return written


def _add_result_submission(
    db: Session,
    user: User,
    contest: Contest,
    problem_code: str,
    *,
    status: str,
    passed_tests: int,
    compile_output: str | None = None,
) -> None:
    """A finished demo submission; tests after `passed_tests` are WA."""
    problem = db.scalar(select(Problem).where(Problem.code == problem_code))
    link = db.get(ContestProblem, (contest.id, problem.id))
    testcases = db.scalars(
        select(Testcase).where(Testcase.problem_id == problem.id).order_by(Testcase.order_index)
    ).all()
    is_ce = status == "CE"
    total = 0 if is_ce else len(testcases)
    submission = Submission(
        user_id=user.id,
        contest_id=contest.id,
        problem_id=problem.id,
        language="cpp17",
        source_code="// demo submission created by the seed script\n",
        max_points=link.max_points,
        status=status,
        score=0 if is_ce else link.max_points * passed_tests // total,
        tests_passed=0 if is_ce else passed_tests,
        tests_total=total,
        time_ms=None if is_ce else 5,
        memory_kb=None if is_ce else 3400,
        compile_output=compile_output,
        judging_started_at=datetime.now(UTC),
        judged_at=datetime.now(UTC),
    )
    db.add(submission)
    db.flush()
    if is_ce:
        return
    for testcase in testcases:
        verdict = "AC" if testcase.order_index <= passed_tests else "WA"
        db.add(
            SubmissionResult(
                submission_id=submission.id,
                testcase_id=testcase.id,
                verdict=verdict,
                time_ms=5,
                memory_kb=3400,
            )
        )


def _ensure_demo_submissions(db: Session, student: User, contest: Contest) -> int:
    has_any = db.scalar(select(Submission.id).where(Submission.user_id == student.id).limit(1))
    if has_any is not None:
        return 0
    _add_result_submission(db, student, contest, "P_MAX_OF_THREE", status="AC", passed_tests=6)
    _add_result_submission(
        db, student, contest, "P_ADD_SUB_MUL_DIV", status="PARTIAL", passed_tests=7
    )
    _add_result_submission(
        db,
        student,
        contest,
        "P_HHMMSS_TO_SECONDS",
        status="CE",
        passed_tests=0,
        compile_output="main.cpp:5:5: error: 'cin' was not declared in this scope\n",
    )
    db.flush()
    return 3


def run_seed(
    db: Session, seed_dir: Path, problems_dir: Path, bcrypt_rounds: int = BCRYPT_ROUNDS
) -> SeedSummary:
    """Apply the seed inside the caller's transaction (the caller commits)."""
    if not seed_dir.is_dir():
        raise FileNotFoundError(f"Seed directory not found: {seed_dir}")
    # Two backend replicas starting together must not seed at the same time.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SEED_LOCK_KEY})
    users_created, users = _ensure_users(db, bcrypt_rounds)
    contest = _ensure_contest(db)
    folders = sorted(path for path in seed_dir.iterdir() if (path / "problem.yaml").is_file())
    files_written = sum(_ensure_problem(db, contest, folder, problems_dir) for folder in folders)
    demo_created = _ensure_demo_submissions(db, users[DEMO_STUDENT], contest)
    return SeedSummary(
        users_created=users_created,
        problems=len(folders),
        testcase_files_written=files_written,
        demo_submissions_created=demo_created,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    if settings.env == "production":
        # The seed creates demo accounts with known passwords (admin/admin123).
        raise SystemExit("Refusing to seed demo data when ENV=production")
    with SessionLocal() as db:
        summary = run_seed(db, Path(settings.seed_dir), Path(settings.problems_dir))
        db.commit()
    logger.info("Seed done: %s", summary)


if __name__ == "__main__":
    main()
