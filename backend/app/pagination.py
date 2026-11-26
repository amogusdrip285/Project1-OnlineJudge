"""Shared pagination (MASTER_PLAN §6.1): `page` starts at 1, `size` max 100."""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Query

MAX_PAGE_SIZE = 100
MAX_PAGE = 1_000_000  # keeps OFFSET far inside BIGINT


@dataclass(frozen=True)
class PageParams:
    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def page_params(default_size: int) -> Any:
    """`Depends(...)` with this endpoint's default page size. Use it inside `Annotated`."""

    def dependency(
        page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
        size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = default_size,
    ) -> PageParams:
        return PageParams(page=page, size=size)

    return Depends(dependency)
