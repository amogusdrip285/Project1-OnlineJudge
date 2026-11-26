from typing import Literal

from app.schemas import ApiModel, Page

Level = Literal["easy", "medium", "hard"]


class ProblemListItem(ApiModel):
    id: int
    code: str
    title: str
    level: Level
    max_points: int
    points_earned: int
    is_complete: bool


class ProblemPage(Page[ProblemListItem]):
    total_points_earned: int
    total_max_points: int


class SampleTest(ApiModel):
    input: str
    output: str


class ProblemDetail(ApiModel):
    id: int
    code: str
    title: str
    statement_md: str
    level: Level
    time_limit_ms: int
    memory_limit_mb: int
    max_points: int
    points_earned: int
    samples: list[SampleTest]
    languages: list[str]
