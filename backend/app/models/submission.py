"""Submissions. Column ownership (MASTER_PLAN §4.3): the backend only INSERTs rows with
status 'PENDING'; the judge owns every status change and all result columns."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import LANGUAGES, SUBMISSION_STATUSES, TEST_VERDICTS, sql_in
from app.models.base import Base, created_at_column


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint(sql_in("language", LANGUAGES), name="language"),
        CheckConstraint(sql_in("status", SUBMISSION_STATUSES), name="status"),
        Index("ix_submissions_pending", "id", postgresql_where=text("status = 'PENDING'")),
        Index("ix_submissions_user_contest_problem", "user_id", "contest_id", "problem_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    contest_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contests.id"))
    problem_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("problems.id"))
    language: Mapped[str] = mapped_column(Text)
    source_code: Mapped[str] = mapped_column(Text)
    max_points: Mapped[int] = mapped_column(Integer)  # snapshot at submit time
    status: Mapped[str] = mapped_column(Text, server_default="PENDING")
    score: Mapped[int] = mapped_column(Integer, server_default="0")
    tests_passed: Mapped[int] = mapped_column(Integer, server_default="0")
    tests_total: Mapped[int] = mapped_column(Integer, server_default="0")
    time_ms: Mapped[int | None] = mapped_column(Integer)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    compile_output: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    judging_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubmissionResult(Base):
    __tablename__ = "submission_results"
    __table_args__ = (CheckConstraint(sql_in("verdict", TEST_VERDICTS), name="verdict"),)

    submission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True
    )
    testcase_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("testcases.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(Text)
    time_ms: Mapped[int] = mapped_column(Integer)
    memory_kb: Mapped[int] = mapped_column(Integer)
