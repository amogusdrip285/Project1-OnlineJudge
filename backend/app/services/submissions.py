"""Submit + read submissions. The backend only INSERTs PENDING rows (MASTER_PLAN §4.3)."""

import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.constants import LANGUAGES
from app.deps import CurrentUser
from app.errors import AppError
from app.models import Problem, Submission, SubmissionResult, Testcase, User
from app.pagination import PageParams
from app.schemas import Page
from app.schemas.submissions import (
    SubmissionDetail,
    SubmissionListItem,
    SubmitResponse,
    TestResultOut,
)
from app.services.contests import get_visible_contest
from app.services.problems import get_contest_problem

PENDING = "PENDING"


def _check_cooldown(db: Session, user_id: int, cooldown_seconds: int) -> None:
    # Lock the user's row so two parallel submits can't both pass the check.
    db.execute(select(User.id).where(User.id == user_id).with_for_update())
    elapsed = db.scalar(
        select(func.extract("epoch", func.now() - func.max(Submission.created_at))).where(
            Submission.user_id == user_id
        )
    )
    if elapsed is None:
        return
    remaining = cooldown_seconds - float(elapsed)
    if remaining > 0:
        seconds = max(1, math.ceil(remaining))
        raise AppError(429, "RATE_LIMITED", f"Please wait {seconds} s before submitting again")


def _validate_source(language: str, source_code: str, max_bytes: int) -> None:
    if language not in LANGUAGES:
        allowed = ", ".join(LANGUAGES)
        raise AppError(400, "VALIDATION_ERROR", f"language: must be one of {allowed}")
    if not source_code.strip():
        raise AppError(400, "VALIDATION_ERROR", "source_code: must not be empty")
    if len(source_code.encode()) > max_bytes:
        raise AppError(
            413, "SOURCE_TOO_LARGE", f"Source code is too large (max {max_bytes // 1024} KB)"
        )


def submit(
    db: Session,
    contest_id: int,
    problem_id: int,
    user: CurrentUser,
    language: str,
    source_code: str,
    settings: Settings,
) -> SubmitResponse:
    _, max_points = get_contest_problem(db, contest_id, problem_id, user)
    _validate_source(language, source_code, settings.max_source_bytes)
    _check_cooldown(db, user.id, settings.submit_cooldown_seconds)

    submission = Submission(
        user_id=user.id,
        contest_id=contest_id,
        problem_id=problem_id,
        language=language,
        source_code=source_code,
        max_points=max_points,
        status=PENDING,
    )
    db.add(submission)
    db.commit()
    return SubmitResponse(submission_id=submission.id, status=PENDING)


def list_submissions(
    db: Session,
    contest_id: int,
    user: CurrentUser,
    params: PageParams,
    problem_id: int | None = None,
    user_id: int | None = None,
) -> Page[SubmissionListItem]:
    get_visible_contest(db, contest_id, user)
    # Students always see their own list; only admins may look at another user.
    owner_id = user_id if (user.is_admin and user_id is not None) else user.id

    filters = [Submission.contest_id == contest_id, Submission.user_id == owner_id]
    if problem_id is not None:
        filters.append(Submission.problem_id == problem_id)

    total = db.scalar(select(func.count()).select_from(Submission).where(*filters)) or 0
    rows = db.execute(
        select(Submission, Problem.title)
        .join(Problem, Problem.id == Submission.problem_id)
        .where(*filters)
        .order_by(Submission.id.desc())
        .offset(params.offset)
        .limit(params.size)
    ).all()
    items = [
        SubmissionListItem(
            id=sub.id,
            problem_id=sub.problem_id,
            problem_title=title,
            language=sub.language,
            status=sub.status,
            score=sub.score,
            max_points=sub.max_points,
            tests_passed=sub.tests_passed,
            tests_total=sub.tests_total,
            time_ms=sub.time_ms,
            memory_kb=sub.memory_kb,
            created_at=sub.created_at,
        )
        for sub, title in rows
    ]
    return Page(items=items, page=params.page, size=params.size, total=total)


def get_submission(db: Session, submission_id: int, user: CurrentUser) -> SubmissionDetail:
    row = db.execute(
        select(Submission, Problem.title)
        .join(Problem, Problem.id == Submission.problem_id)
        .where(Submission.id == submission_id)
    ).first()
    # 404 (not 403) for someone else's submission, so its existence isn't revealed.
    if row is None or (row[0].user_id != user.id and not user.is_admin):
        raise AppError(404, "NOT_FOUND", "Submission not found")
    sub, title = row

    results = db.execute(
        select(Testcase.order_index, SubmissionResult)
        .join(Testcase, Testcase.id == SubmissionResult.testcase_id)
        .where(SubmissionResult.submission_id == sub.id)
        .order_by(Testcase.order_index)
    ).all()
    return SubmissionDetail(
        id=sub.id,
        contest_id=sub.contest_id,
        problem_id=sub.problem_id,
        problem_title=title,
        language=sub.language,
        source_code=sub.source_code,
        status=sub.status,
        score=sub.score,
        max_points=sub.max_points,
        tests_passed=sub.tests_passed,
        tests_total=sub.tests_total,
        time_ms=sub.time_ms,
        memory_kb=sub.memory_kb,
        compile_output=sub.compile_output,
        created_at=sub.created_at,
        judged_at=sub.judged_at,
        results=[
            TestResultOut(
                order_index=order_index,
                verdict=result.verdict,
                time_ms=result.time_ms,
                memory_kb=result.memory_kb,
            )
            for order_index, result in results
        ],
    )
