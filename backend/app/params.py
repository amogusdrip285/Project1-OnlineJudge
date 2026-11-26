"""Bounded path/query parameter types, so out-of-range input is a 400, not a DB error."""

from typing import Annotated

from fastapi import Path, Query

MAX_ID = 2**63 - 1  # BIGINT
NO_NUL_PATTERN = r"^[^\x00]*$"  # Postgres text cannot store NUL bytes

IdPath = Annotated[int, Path(ge=1, le=MAX_ID)]
OptionalIdQuery = Annotated[int | None, Query(ge=1, le=MAX_ID)]
