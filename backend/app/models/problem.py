from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.constants import LEVELS, sql_in
from app.models.base import Base, created_at_column


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (CheckConstraint(sql_in("level", LEVELS), name="level"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    statement_md: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(Text)
    time_limit_ms: Mapped[int] = mapped_column(Integer, server_default="1000")
    memory_limit_mb: Mapped[int] = mapped_column(Integer, server_default="256")
    created_at: Mapped[datetime] = created_at_column()


class Testcase(Base):
    __tablename__ = "testcases"
    __table_args__ = (UniqueConstraint("problem_id", "order_index"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("problems.id", ondelete="CASCADE")
    )
    order_index: Mapped[int] = mapped_column(Integer)
    input_path: Mapped[str] = mapped_column(Text)  # relative to PROBLEMS_DIR
    output_path: Mapped[str] = mapped_column(Text)  # relative to PROBLEMS_DIR
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=expression.false())
