from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.deps import CurrentUser
from app.errors import AppError
from app.models import Contest, ContestProblem
from app.pagination import PageParams
from app.schemas import Page
from app.schemas.contests import ContestDetail, ContestListItem


def _visible(query: Select, user: CurrentUser) -> Select:
    return query if user.is_admin else query.where(Contest.is_public.is_(True))


def get_visible_contest(db: Session, contest_id: int, user: CurrentUser) -> Contest:
    """The contest, or 404 when it doesn't exist or the student can't see it."""
    contest = db.scalar(_visible(select(Contest).where(Contest.id == contest_id), user))
    if contest is None:
        raise AppError(404, "NOT_FOUND", "Contest not found")
    return contest


def list_contests(db: Session, user: CurrentUser, params: PageParams) -> Page[ContestListItem]:
    problem_count = (
        select(func.count())
        .where(ContestProblem.contest_id == Contest.id)
        .correlate(Contest)
        .scalar_subquery()
    )
    total = db.scalar(_visible(select(func.count()).select_from(Contest), user)) or 0
    rows = db.execute(
        _visible(select(Contest, problem_count.label("problem_count")), user)
        .order_by(Contest.start_time.desc().nulls_last(), Contest.id.desc())
        .offset(params.offset)
        .limit(params.size)
    ).all()
    items = [
        ContestListItem(
            id=contest.id,
            code=contest.code,
            title=contest.title,
            start_time=contest.start_time,
            end_time=contest.end_time,
            problem_count=count,
        )
        for contest, count in rows
    ]
    return Page(items=items, page=params.page, size=params.size, total=total)


def get_contest(db: Session, contest_id: int, user: CurrentUser) -> ContestDetail:
    return ContestDetail.model_validate(get_visible_contest(db, contest_id, user))
