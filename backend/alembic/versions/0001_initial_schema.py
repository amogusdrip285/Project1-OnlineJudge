"""Initial MVP schema (MASTER_PLAN §4.2).

Revision ID: 0001
Revises:
Create Date: 2026-11-20

Values are written out literally (not imported from app.constants) so this migration never
changes when the app code changes later. Add new values in a new migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), primary_key=True)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "users",
        _id(),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        _created_at(),
        sa.CheckConstraint("role IN ('student','admin')", name="role"),
    )

    op.create_table(
        "contests",
        _id(),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        _created_at(),
    )

    op.create_table(
        "problems",
        _id(),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("statement_md", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("time_limit_ms", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("memory_limit_mb", sa.Integer(), nullable=False, server_default="256"),
        _created_at(),
        sa.CheckConstraint("level IN ('easy','medium','hard')", name="level"),
    )

    op.create_table(
        "contest_problems",
        sa.Column(
            "contest_id",
            sa.BigInteger(),
            sa.ForeignKey("contests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "problem_id",
            sa.BigInteger(),
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("max_points", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.CheckConstraint("max_points > 0", name="max_points_positive"),
    )

    op.create_table(
        "testcases",
        _id(),
        sa.Column(
            "problem_id",
            sa.BigInteger(),
            sa.ForeignKey("problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("input_path", sa.Text(), nullable=False),
        sa.Column("output_path", sa.Text(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("problem_id", "order_index"),
    )

    op.create_table(
        "submissions",
        _id(),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("contest_id", sa.BigInteger(), sa.ForeignKey("contests.id"), nullable=False),
        sa.Column("problem_id", sa.BigInteger(), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("max_points", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tests_passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tests_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_ms", sa.Integer(), nullable=True),
        sa.Column("memory_kb", sa.Integer(), nullable=True),
        sa.Column("compile_output", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("judging_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("language IN ('cpp17','python3')", name="language"),
        sa.CheckConstraint(
            "status IN ('PENDING','JUDGING','AC','WA','TLE','MLE','RE','CE','PARTIAL','SE')",
            name="status",
        ),
    )
    op.create_index(
        "ix_submissions_pending",
        "submissions",
        ["id"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_submissions_user_contest_problem",
        "submissions",
        ["user_id", "contest_id", "problem_id"],
    )

    op.create_table(
        "submission_results",
        sa.Column(
            "submission_id",
            sa.BigInteger(),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "testcase_id",
            sa.BigInteger(),
            sa.ForeignKey("testcases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("time_ms", sa.Integer(), nullable=False),
        sa.Column("memory_kb", sa.Integer(), nullable=False),
        sa.CheckConstraint("verdict IN ('AC','WA','TLE','MLE','RE')", name="verdict"),
    )


def downgrade() -> None:
    op.drop_table("submission_results")
    op.drop_index("ix_submissions_user_contest_problem", table_name="submissions")
    op.drop_index("ix_submissions_pending", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("testcases")
    op.drop_table("contest_problems")
    op.drop_table("problems")
    op.drop_table("contests")
    op.drop_table("users")
