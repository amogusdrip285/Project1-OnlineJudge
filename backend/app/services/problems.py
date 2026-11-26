from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.constants import LANGUAGES
from app.deps import CurrentUser
from app.errors import AppError
from app.models import ContestProblem, Problem, Testcase
from app.pagination import PageParams
from app.schemas.problems import ProblemDetail, ProblemListItem, ProblemPage, SampleTest
from app.services.contests import get_visible_contest
from app.services.scoring import best_scores
from app.services.testcase_storage import read_sample_file

LIKE_ESCAPE = "\\"


def _like_pattern(search: str) -> str:
    """`%term%` with the user's own `%`, `_` and `\\` treated as plain characters."""
    escaped = (
        search.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )
    return f"%{escaped}%"


def list_problems(
    db: Session, contest_id: int, user: CurrentUser, search: str | None, params: PageParams
) -> ProblemPage:
    get_visible_contest(db, contest_id, user)

    base = (
        select(Problem, ContestProblem.max_points)
        .join(ContestProblem, ContestProblem.problem_id == Problem.id)
        .where(ContestProblem.contest_id == contest_id)
    )
    term = (search or "").strip()
    filtered = base
    if term:
        pattern = _like_pattern(term)
        filtered = base.where(
            or_(
                Problem.title.ilike(pattern, escape=LIKE_ESCAPE),
                Problem.code.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )

    total = db.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    rows = db.execute(
        filtered.order_by(ContestProblem.order_index, Problem.id)
        .offset(params.offset)
        .limit(params.size)
    ).all()

    # Totals cover every problem of the contest, ignoring search and paging.
    all_max_points = dict(
        db.execute(
            select(ContestProblem.problem_id, ContestProblem.max_points).where(
                ContestProblem.contest_id == contest_id
            )
        ).all()
    )
    scores = best_scores(db, user.id, contest_id)

    items = [
        ProblemListItem(
            id=problem.id,
            code=problem.code,
            title=problem.title,
            level=problem.level,
            max_points=max_points,
            points_earned=scores.get(problem.id, 0),
            is_complete=scores.get(problem.id, 0) == max_points,
        )
        for problem, max_points in rows
    ]
    return ProblemPage(
        items=items,
        page=params.page,
        size=params.size,
        total=total,
        total_points_earned=sum(scores.get(pid, 0) for pid in all_max_points),
        total_max_points=sum(all_max_points.values()),
    )


def get_contest_problem(
    db: Session, contest_id: int, problem_id: int, user: CurrentUser
) -> tuple[Problem, int]:
    """(problem, max_points) for a problem attached to a visible contest, else 404."""
    get_visible_contest(db, contest_id, user)
    row = db.execute(
        select(Problem, ContestProblem.max_points)
        .join(ContestProblem, ContestProblem.problem_id == Problem.id)
        .where(ContestProblem.contest_id == contest_id, Problem.id == problem_id)
    ).first()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Problem not found")
    return row[0], row[1]


def _load_samples(db: Session, problem_id: int, problems_dir: str) -> list[SampleTest]:
    testcases = db.scalars(
        select(Testcase)
        .where(Testcase.problem_id == problem_id, Testcase.is_sample.is_(True))
        .order_by(Testcase.order_index)
    ).all()
    samples = []
    for testcase in testcases:
        sample_input = read_sample_file(problems_dir, testcase.input_path)
        sample_output = read_sample_file(problems_dir, testcase.output_path)
        if sample_input is not None and sample_output is not None:
            samples.append(SampleTest(input=sample_input, output=sample_output))
    return samples


def get_problem_detail(
    db: Session, contest_id: int, problem_id: int, user: CurrentUser, problems_dir: str
) -> ProblemDetail:
    problem, max_points = get_contest_problem(db, contest_id, problem_id, user)
    points = best_scores(db, user.id, contest_id).get(problem.id, 0)
    return ProblemDetail(
        id=problem.id,
        code=problem.code,
        title=problem.title,
        statement_md=problem.statement_md,
        level=problem.level,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        max_points=max_points,
        points_earned=points,
        samples=_load_samples(db, problem.id, problems_dir),
        languages=list(LANGUAGES),
    )
