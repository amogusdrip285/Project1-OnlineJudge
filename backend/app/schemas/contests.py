from app.schemas import ApiModel, UtcDatetime


class ContestListItem(ApiModel):
    id: int
    code: str
    title: str
    start_time: UtcDatetime | None
    end_time: UtcDatetime | None
    problem_count: int


class ContestDetail(ApiModel):
    id: int
    code: str
    title: str
    description: str
    start_time: UtcDatetime | None
    end_time: UtcDatetime | None
