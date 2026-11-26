"""Points earned = the user's best score per problem in a contest (MASTER_PLAN §6.2)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Submission


def best_scores(db: Session, user_id: int, contest_id: int) -> dict[int, int]:
    """{problem_id: MAX(score)} for one user in one contest, in a single GROUP BY query."""
    rows = db.execute(
        select(Submission.problem_id, func.max(Submission.score))
        .where(Submission.user_id == user_id, Submission.contest_id == contest_id)
        .group_by(Submission.problem_id)
    ).all()
    return {problem_id: score for problem_id, score in rows}
