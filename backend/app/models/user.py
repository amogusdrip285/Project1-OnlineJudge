from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import ROLES, sql_in
from app.models.base import Base, created_at_column


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(sql_in("role", ROLES), name="role"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
