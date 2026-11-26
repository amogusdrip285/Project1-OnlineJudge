"""Pydantic request/response models. Field names match MASTER_PLAN §6.2 exactly."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


def _to_utc_iso(value: datetime) -> str:
    """`2026-11-20T09:49:00Z`: UTC, whole seconds, `Z` suffix (MASTER_PLAN §6.1)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_to_utc_iso, return_type=str)]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)


class Page[T](ApiModel):
    items: list[T]
    page: int
    size: int
    total: int
