"""Student-facing contest, problem and submission endpoints (MASTER_PLAN §6.2)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import AppSettings, AuthUser, DbSession
from app.pagination import PageParams, page_params
from app.params import NO_NUL_PATTERN, IdPath, OptionalIdQuery
from app.schemas import Page
from app.schemas.contests import ContestDetail, ContestListItem
from app.schemas.problems import ProblemDetail, ProblemPage
from app.schemas.submissions import (
    SubmissionDetail,
    SubmissionListItem,
    SubmitRequest,
    SubmitResponse,
)
from app.services import contests, problems, submissions

CONTEST_PAGE_SIZE = 5
PROBLEM_PAGE_SIZE = 5
SUBMISSION_PAGE_SIZE = 10
MAX_SEARCH_LENGTH = 100

SearchQuery = Annotated[str | None, Query(max_length=MAX_SEARCH_LENGTH, pattern=NO_NUL_PATTERN)]
ContestPageParams = Annotated[PageParams, page_params(CONTEST_PAGE_SIZE)]
ProblemPageParams = Annotated[PageParams, page_params(PROBLEM_PAGE_SIZE)]
SubmissionPageParams = Annotated[PageParams, page_params(SUBMISSION_PAGE_SIZE)]

router = APIRouter(tags=["contests"])


@router.get("/contests")
def list_contests(
    db: DbSession, user: AuthUser, params: ContestPageParams
) -> Page[ContestListItem]:
    return contests.list_contests(db, user, params)


@router.get("/contests/{contest_id}")
def get_contest(contest_id: IdPath, db: DbSession, user: AuthUser) -> ContestDetail:
    return contests.get_contest(db, contest_id, user)


@router.get("/contests/{contest_id}/problems")
def list_problems(
    contest_id: IdPath,
    db: DbSession,
    user: AuthUser,
    params: ProblemPageParams,
    search: SearchQuery = None,
) -> ProblemPage:
    return problems.list_problems(db, contest_id, user, search, params)


@router.get("/contests/{contest_id}/problems/{problem_id}")
def get_problem(
    contest_id: IdPath, problem_id: IdPath, db: DbSession, user: AuthUser, settings: AppSettings
) -> ProblemDetail:
    return problems.get_problem_detail(db, contest_id, problem_id, user, settings.problems_dir)


@router.post("/contests/{contest_id}/problems/{problem_id}/submit", status_code=201)
def submit(
    contest_id: IdPath,
    problem_id: IdPath,
    body: SubmitRequest,
    db: DbSession,
    user: AuthUser,
    settings: AppSettings,
) -> SubmitResponse:
    return submissions.submit(
        db, contest_id, problem_id, user, body.language, body.source_code, settings
    )


@router.get("/contests/{contest_id}/submissions")
def list_submissions(
    contest_id: IdPath,
    db: DbSession,
    user: AuthUser,
    params: SubmissionPageParams,
    problem_id: OptionalIdQuery = None,
    user_id: OptionalIdQuery = None,
) -> Page[SubmissionListItem]:
    return submissions.list_submissions(db, contest_id, user, params, problem_id, user_id)


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: IdPath, db: DbSession, user: AuthUser) -> SubmissionDetail:
    return submissions.get_submission(db, submission_id, user)
