"""Import every model here so `Base.metadata` knows all tables (used by Alembic)."""

from app.models.base import Base
from app.models.contest import Contest, ContestProblem
from app.models.problem import Problem, Testcase
from app.models.submission import Submission, SubmissionResult
from app.models.user import User

__all__ = [
    "Base",
    "Contest",
    "ContestProblem",
    "Problem",
    "Submission",
    "SubmissionResult",
    "Testcase",
    "User",
]
