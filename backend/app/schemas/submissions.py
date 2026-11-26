from pydantic import Field, field_validator

from app.schemas import ApiModel, UtcDatetime

# Parse-time cap far above MAX_SOURCE_BYTES, only to reject absurd bodies early. The real,
# configurable limit (413) is checked in the service after the 404 checks.
SOURCE_PARSE_MAX_CHARS = 1_000_000


class SubmitRequest(ApiModel):
    # Language and size are checked in the service, after the 404 checks
    # (WEEK2_PLAN §2.2 "Order of checks").
    language: str = Field(max_length=32)
    source_code: str = Field(max_length=SOURCE_PARSE_MAX_CHARS)

    @field_validator("language", "source_code")
    @classmethod
    def _no_nul_bytes(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("must not contain NUL bytes")
        return value


class SubmitResponse(ApiModel):
    submission_id: int
    status: str


class SubmissionListItem(ApiModel):
    id: int
    problem_id: int
    problem_title: str
    language: str
    status: str
    score: int
    max_points: int
    tests_passed: int
    tests_total: int
    time_ms: int | None
    memory_kb: int | None
    created_at: UtcDatetime


class TestResultOut(ApiModel):
    order_index: int
    verdict: str
    time_ms: int
    memory_kb: int


class SubmissionDetail(ApiModel):
    id: int
    contest_id: int
    problem_id: int
    problem_title: str
    language: str
    source_code: str
    status: str
    score: int
    max_points: int
    tests_passed: int
    tests_total: int
    time_ms: int | None
    memory_kb: int | None
    compile_output: str | None
    created_at: UtcDatetime
    judged_at: UtcDatetime | None
    results: list[TestResultOut]
