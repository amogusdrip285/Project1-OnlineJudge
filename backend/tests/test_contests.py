from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Contest, ContestProblem, Submission, SubmissionResult
from tests.conftest import TEST_JWT_SECRET
from tests.factories import attach, auth_header, make_contest, make_problem, make_user


def _clear_contests(db: Session) -> None:
    """The shared test DB may hold rows from a manual seed run; start each list test empty."""
    db.execute(delete(SubmissionResult))
    db.execute(delete(Submission))
    db.execute(delete(ContestProblem))
    db.execute(delete(Contest))


def test_list_requires_login(api: TestClient) -> None:
    assert api.get("/api/contests").status_code == 401


def test_list_shape_and_problem_count(api: TestClient, db: Session) -> None:
    _clear_contests(db)
    student = make_user(db)
    contest = make_contest(
        db,
        code="project120261",
        title="Project 1 - 2026.1",
        start_time=datetime(2026, 9, 1, tzinfo=UTC),
        end_time=datetime(2027, 1, 15, tzinfo=UTC),
    )
    for index in range(3):
        attach(db, contest, make_problem(db), order_index=index)

    response = api.get("/api/contests", headers=auth_header(student, TEST_JWT_SECRET))

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": contest.id,
                "code": "project120261",
                "title": "Project 1 - 2026.1",
                "start_time": "2026-09-01T00:00:00Z",
                "end_time": "2027-01-15T00:00:00Z",
                "problem_count": 3,
            }
        ],
        "page": 1,
        "size": 5,
        "total": 1,
    }


def test_students_do_not_see_private_contests_but_admins_do(api: TestClient, db: Session) -> None:
    _clear_contests(db)
    make_contest(db, code="public_one")
    make_contest(db, code="private_one", is_public=False)
    student = make_user(db)
    admin = make_user(db, role="admin")

    student_codes = [
        c["code"]
        for c in api.get("/api/contests", headers=auth_header(student, TEST_JWT_SECRET)).json()[
            "items"
        ]
    ]
    admin_body = api.get("/api/contests", headers=auth_header(admin, TEST_JWT_SECRET)).json()

    assert student_codes == ["public_one"]
    assert admin_body["total"] == 2


def test_list_is_sorted_newest_start_first_and_paginated(api: TestClient, db: Session) -> None:
    _clear_contests(db)
    student = make_user(db)
    for month in (1, 3, 2):
        make_contest(db, code=f"c{month}", start_time=datetime(2026, month, 1, tzinfo=UTC))
    make_contest(db, code="no_start")

    response = api.get("/api/contests?page=1&size=2", headers=auth_header(student, TEST_JWT_SECRET))
    second_page = api.get(
        "/api/contests?page=2&size=2", headers=auth_header(student, TEST_JWT_SECRET)
    )

    assert [c["code"] for c in response.json()["items"]] == ["c3", "c2"]
    assert [c["code"] for c in second_page.json()["items"]] == ["c1", "no_start"]
    assert response.json()["total"] == 4


def test_invalid_pagination_is_400(api: TestClient, db: Session) -> None:
    headers = auth_header(make_user(db), TEST_JWT_SECRET)

    assert api.get("/api/contests?size=101", headers=headers).status_code == 400
    assert api.get("/api/contests?page=0", headers=headers).status_code == 400


def test_detail_shape(api: TestClient, db: Session) -> None:
    contest = make_contest(db, title="Weekly", description="Weekly exercises")

    response = api.get(
        f"/api/contests/{contest.id}", headers=auth_header(make_user(db), TEST_JWT_SECRET)
    )

    assert response.json() == {
        "id": contest.id,
        "code": contest.code,
        "title": "Weekly",
        "description": "Weekly exercises",
        "start_time": None,
        "end_time": None,
    }


def test_private_contest_detail_is_404_for_student(api: TestClient, db: Session) -> None:
    contest = make_contest(db, is_public=False)

    student = api.get(
        f"/api/contests/{contest.id}", headers=auth_header(make_user(db), TEST_JWT_SECRET)
    )
    admin = api.get(
        f"/api/contests/{contest.id}",
        headers=auth_header(make_user(db, role="admin"), TEST_JWT_SECRET),
    )

    assert student.status_code == 404
    assert admin.status_code == 200


def test_unknown_contest_is_404(api: TestClient, db: Session) -> None:
    headers = auth_header(make_user(db), TEST_JWT_SECRET)

    response = api.get("/api/contests/999999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
