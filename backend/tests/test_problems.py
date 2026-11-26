from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Contest, Problem, User
from tests.conftest import TEST_JWT_SECRET
from tests.factories import (
    attach,
    auth_header,
    make_contest,
    make_problem,
    make_submission,
    make_testcase,
    make_user,
)


@pytest.fixture
def student(db: Session) -> User:
    return make_user(db)


@pytest.fixture
def headers(student: User) -> dict[str, str]:
    return auth_header(student, TEST_JWT_SECRET)


@dataclass(frozen=True)
class Catalog:
    contest: Contest
    problems: dict[str, Problem]


@pytest.fixture
def catalog(db: Session) -> Catalog:
    """Problems: ADD (100 pts), HMS (140 pts), UPPER (100 pts), in that order."""
    contest = make_contest(db)
    specs = [
        ("T_ADD", "Week 1 - Add two numbers", 100),
        ("T_HMS", "Week 1 - Convert hh:mm:ss", 140),
        ("T_UPPER", "Week 1 - Uppercase 100%_done", 100),
    ]
    problems = {}
    for order, (code, title, points) in enumerate(specs, start=1):
        problems[code] = make_problem(db, code=code, title=title)
        attach(db, contest, problems[code], max_points=points, order_index=order)
    return Catalog(contest=contest, problems=problems)


@pytest.fixture
def contest(catalog: Catalog) -> Contest:
    return catalog.contest


def _problems(api: TestClient, contest: Contest, headers: dict, query: str = "") -> dict:
    response = api.get(f"/api/contests/{contest.id}/problems{query}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_list_without_submissions(api: TestClient, contest: Contest, headers: dict) -> None:
    body = _problems(api, contest, headers)

    assert [item["code"] for item in body["items"]] == ["T_ADD", "T_HMS", "T_UPPER"]
    assert body["items"][0] == {
        "id": body["items"][0]["id"],
        "code": "T_ADD",
        "title": "Week 1 - Add two numbers",
        "level": "easy",
        "max_points": 100,
        "points_earned": 0,
        "is_complete": False,
    }
    assert body["total"] == 3
    assert body["total_points_earned"] == 0
    assert body["total_max_points"] == 340


def test_points_are_best_score_and_complete_only_at_max(
    api: TestClient, db: Session, catalog: Catalog, student: User, headers: dict
) -> None:
    contest = catalog.contest
    add, hms = catalog.problems["T_ADD"], catalog.problems["T_HMS"]
    make_submission(db, student, contest, add, status="PARTIAL", score=70)
    make_submission(db, student, contest, add, status="AC", score=100)
    make_submission(db, student, contest, add, status="WA", score=0)
    make_submission(db, student, contest, hms, status="PARTIAL", score=56, max_points=140)
    other = make_user(db)
    make_submission(db, other, contest, hms, status="AC", score=140, max_points=140)

    body = _problems(api, contest, headers)
    by_code = {item["code"]: item for item in body["items"]}

    assert by_code["T_ADD"]["points_earned"] == 100
    assert by_code["T_ADD"]["is_complete"] is True
    assert by_code["T_HMS"]["points_earned"] == 56
    assert by_code["T_HMS"]["is_complete"] is False
    assert body["total_points_earned"] == 156


def test_search_matches_title_or_code_case_insensitive(
    api: TestClient, contest: Contest, headers: dict
) -> None:
    by_title = _problems(api, contest, headers, "?search=convert")
    by_code = _problems(api, contest, headers, "?search=t_add")

    assert [item["code"] for item in by_title["items"]] == ["T_HMS"]
    assert [item["code"] for item in by_code["items"]] == ["T_ADD"]
    assert by_title["total"] == 1
    # Totals still cover the whole contest.
    assert by_title["total_max_points"] == 340


def test_search_treats_wildcards_literally(
    api: TestClient, contest: Contest, headers: dict
) -> None:
    percent = _problems(api, contest, headers, "?search=100%25_")
    underscore_only = _problems(api, contest, headers, "?search=_")

    assert [item["code"] for item in percent["items"]] == ["T_UPPER"]
    # "_" is literal: only codes/titles containing an underscore match (all three codes do).
    assert underscore_only["total"] == 3


def test_blank_search_is_no_filter(api: TestClient, contest: Contest, headers: dict) -> None:
    assert _problems(api, contest, headers, "?search=%20%20")["total"] == 3


def test_pagination(api: TestClient, contest: Contest, headers: dict) -> None:
    body = _problems(api, contest, headers, "?page=2&size=2")

    assert [item["code"] for item in body["items"]] == ["T_UPPER"]
    assert (body["page"], body["size"], body["total"]) == (2, 2, 3)


def test_list_of_private_contest_is_404_for_student(
    api: TestClient, db: Session, headers: dict
) -> None:
    contest = make_contest(db, is_public=False)

    response = api.get(f"/api/contests/{contest.id}/problems", headers=headers)

    assert response.status_code == 404


def test_detail_with_samples_from_files(
    api: TestClient, db: Session, settings: Settings, headers: dict
) -> None:
    contest = make_contest(db)
    problem = make_problem(db, code="T_DETAIL", time_limit_ms=2000, memory_limit_mb=128)
    attach(db, contest, problem, max_points=120)
    first = make_testcase(db, problem, 1, is_sample=True)
    make_testcase(db, problem, 2, is_sample=False)
    missing = make_testcase(db, problem, 3, is_sample=True)  # files not written: skipped
    base = Path(settings.problems_dir)
    for path, content in ((first.input_path, "3 5\n"), (first.output_path, "8\n")):
        (base / path).parent.mkdir(parents=True, exist_ok=True)
        (base / path).write_text(content, newline="\n")
    assert not (base / missing.input_path).exists()

    response = api.get(f"/api/contests/{contest.id}/problems/{problem.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["samples"] == [{"input": "3 5\n", "output": "8\n"}]
    assert body["time_limit_ms"] == 2000
    assert body["memory_limit_mb"] == 128
    assert body["max_points"] == 120
    assert body["points_earned"] == 0
    assert body["languages"] == ["cpp17", "python3"]
    assert body["statement_md"] == "Statement"


def test_detail_of_problem_not_in_contest_is_404(
    api: TestClient, db: Session, headers: dict
) -> None:
    contest = make_contest(db)
    loose_problem = make_problem(db)

    response = api.get(f"/api/contests/{contest.id}/problems/{loose_problem.id}", headers=headers)

    assert response.status_code == 404
