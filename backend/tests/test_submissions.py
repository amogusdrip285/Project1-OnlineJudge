from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Contest, Problem, Submission, User
from tests.conftest import TEST_JWT_SECRET
from tests.factories import (
    attach,
    auth_header,
    make_contest,
    make_problem,
    make_result,
    make_submission,
    make_testcase,
    make_user,
)

CPP_SOURCE = "#include <bits/stdc++.h>\nint main() { return 0; }\n"
LONG_AGO = datetime.now(UTC) - timedelta(minutes=10)


@pytest.fixture
def student(db: Session) -> User:
    return make_user(db)


@pytest.fixture
def contest(db: Session) -> Contest:
    return make_contest(db)


@pytest.fixture
def problem(db: Session, contest: Contest) -> Problem:
    problem = make_problem(db, title="Week 1 - Add")
    attach(db, contest, problem, max_points=120)
    return problem


def _submit_url(contest: Contest, problem: Problem) -> str:
    return f"/api/contests/{contest.id}/problems/{problem.id}/submit"


def _submit(api: TestClient, user: User, contest: Contest, problem: Problem, **body):
    payload = {"language": "cpp17", "source_code": CPP_SOURCE, **body}
    return api.post(
        _submit_url(contest, problem), json=payload, headers=auth_header(user, TEST_JWT_SECRET)
    )


# --- submit ---


def test_submit_inserts_pending_row_with_max_points_snapshot(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    response = _submit(api, student, contest, problem)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    row = db.get_one(Submission, body["submission_id"])
    assert (row.user_id, row.status, row.max_points, row.language) == (
        student.id,
        "PENDING",
        120,
        "cpp17",
    )
    assert row.source_code == CPP_SOURCE


def test_submit_python(api: TestClient, student: User, contest: Contest, problem: Problem) -> None:
    response = _submit(api, student, contest, problem, language="python3", source_code="print(1)")

    assert response.status_code == 201


def test_submit_unknown_language_is_400(
    api: TestClient, student: User, contest: Contest, problem: Problem
) -> None:
    response = _submit(api, student, contest, problem, language="java17")

    assert response.status_code == 400
    assert "language" in response.json()["error"]["message"]


def test_submit_blank_source_is_400(
    api: TestClient, student: User, contest: Contest, problem: Problem
) -> None:
    response = _submit(api, student, contest, problem, source_code="  \n ")

    assert response.status_code == 400


def test_submit_too_large_is_413(
    api: TestClient, student: User, contest: Contest, problem: Problem
) -> None:
    # 32769 two-byte characters = 65538 bytes, just over the 64 KB limit.
    response = _submit(api, student, contest, problem, source_code="é" * 32769)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "SOURCE_TOO_LARGE"


def test_submit_within_cooldown_is_429_with_seconds_left(
    api: TestClient, student: User, contest: Contest, problem: Problem
) -> None:
    assert _submit(api, student, contest, problem).status_code == 201

    response = _submit(api, student, contest, problem)

    assert response.status_code == 429
    assert response.json()["error"] == {
        "code": "RATE_LIMITED",
        "message": "Please wait 5 s before submitting again",
    }


def test_submit_after_cooldown_is_allowed(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    make_submission(db, student, contest, problem, created_at=LONG_AGO)

    assert _submit(api, student, contest, problem).status_code == 201


def test_cooldown_is_per_user(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    assert _submit(api, student, contest, problem).status_code == 201

    assert _submit(api, make_user(db), contest, problem).status_code == 201


def test_submit_to_problem_outside_contest_is_404_before_validation(
    api: TestClient, db: Session, student: User, contest: Contest
) -> None:
    loose = make_problem(db)

    response = _submit(api, student, contest, loose, language="cobol")

    assert response.status_code == 404


def test_submit_requires_login(api: TestClient, contest: Contest, problem: Problem) -> None:
    response = api.post(
        _submit_url(contest, problem), json={"language": "cpp17", "source_code": CPP_SOURCE}
    )

    assert response.status_code == 401


# --- list ---


def test_list_is_own_newest_first_with_problem_title(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    first = make_submission(db, student, contest, problem, status="WA", max_points=120)
    second = make_submission(
        db,
        student,
        contest,
        problem,
        status="AC",
        score=120,
        max_points=120,
        tests_passed=10,
        tests_total=10,
        time_ms=12,
        memory_kb=3420,
        created_at=datetime(2026, 11, 20, 9, 40, tzinfo=UTC),
    )
    make_submission(db, make_user(db), contest, problem)  # someone else's

    response = api.get(
        f"/api/contests/{contest.id}/submissions", headers=auth_header(student, TEST_JWT_SECRET)
    )

    body = response.json()
    assert [item["id"] for item in body["items"]] == [second.id, first.id]
    assert (body["page"], body["size"], body["total"]) == (1, 10, 2)
    assert body["items"][0] == {
        "id": second.id,
        "problem_id": problem.id,
        "problem_title": "Week 1 - Add",
        "language": "cpp17",
        "status": "AC",
        "score": 120,
        "max_points": 120,
        "tests_passed": 10,
        "tests_total": 10,
        "time_ms": 12,
        "memory_kb": 3420,
        "created_at": "2026-11-20T09:40:00Z",
    }


def test_list_filters_by_problem(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    other_problem = make_problem(db)
    attach(db, contest, other_problem, order_index=2)
    make_submission(db, student, contest, problem)
    make_submission(db, student, contest, other_problem)

    body = api.get(
        f"/api/contests/{contest.id}/submissions?problem_id={problem.id}",
        headers=auth_header(student, TEST_JWT_SECRET),
    ).json()

    assert [item["problem_id"] for item in body["items"]] == [problem.id]


def test_student_cannot_list_another_users_submissions(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    victim = make_user(db)
    make_submission(db, victim, contest, problem)

    body = api.get(
        f"/api/contests/{contest.id}/submissions?user_id={victim.id}",
        headers=auth_header(student, TEST_JWT_SECRET),
    ).json()

    assert body["total"] == 0


def test_admin_can_list_a_users_submissions(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    make_submission(db, student, contest, problem)
    admin = make_user(db, role="admin")

    body = api.get(
        f"/api/contests/{contest.id}/submissions?user_id={student.id}",
        headers=auth_header(admin, TEST_JWT_SECRET),
    ).json()

    assert body["total"] == 1


# --- detail ---


def test_detail_of_judged_submission_has_sorted_results(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    tc2 = make_testcase(db, problem, 2)
    tc1 = make_testcase(db, problem, 1)
    sub = make_submission(
        db,
        student,
        contest,
        problem,
        status="PARTIAL",
        score=60,
        max_points=120,
        tests_passed=1,
        tests_total=2,
        judged_at=datetime(2026, 11, 20, 9, 40, 3, tzinfo=UTC),
    )
    make_result(db, sub, tc2, "TLE")
    make_result(db, sub, tc1, "AC")

    body = api.get(
        f"/api/submissions/{sub.id}", headers=auth_header(student, TEST_JWT_SECRET)
    ).json()

    assert body["status"] == "PARTIAL"
    assert body["contest_id"] == contest.id
    assert body["problem_title"] == "Week 1 - Add"
    assert body["source_code"] == "int main() {}"
    assert body["judged_at"] == "2026-11-20T09:40:03Z"
    assert body["results"] == [
        {"order_index": 1, "verdict": "AC", "time_ms": 3, "memory_kb": 3300},
        {"order_index": 2, "verdict": "TLE", "time_ms": 3, "memory_kb": 3300},
    ]


def test_detail_of_pending_submission(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    sub = make_submission(db, student, contest, problem)

    body = api.get(
        f"/api/submissions/{sub.id}", headers=auth_header(student, TEST_JWT_SECRET)
    ).json()

    assert (body["status"], body["score"], body["results"], body["judged_at"]) == (
        "PENDING",
        0,
        [],
        None,
    )
    assert body["compile_output"] is None


def test_other_students_submission_is_404(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    sub = make_submission(db, make_user(db), contest, problem)

    response = api.get(f"/api/submissions/{sub.id}", headers=auth_header(student, TEST_JWT_SECRET))

    assert response.status_code == 404


def test_admin_can_open_any_submission(
    api: TestClient, db: Session, student: User, contest: Contest, problem: Problem
) -> None:
    sub = make_submission(db, student, contest, problem)
    admin = make_user(db, role="admin")

    response = api.get(f"/api/submissions/{sub.id}", headers=auth_header(admin, TEST_JWT_SECRET))

    assert response.status_code == 200


def test_unknown_submission_is_404(api: TestClient, student: User) -> None:
    response = api.get("/api/submissions/999999999", headers=auth_header(student, TEST_JWT_SECRET))

    assert response.status_code == 404
