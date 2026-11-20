from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.models.base import Base, created_at_column


class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_public: Mapped[bool] = mapped_column(Boolean, server_default=expression.true())
    created_at: Mapped[datetime] = created_at_column()


class ContestProblem(Base):
    __tablename__ = "contest_problems"
    __table_args__ = (CheckConstraint("max_points > 0", name="max_points_positive"),)

    contest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True
    )
    problem_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    )
    max_points: Mapped[int] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer)
