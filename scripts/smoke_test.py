"""End-to-end smoke test for milestone M2 (WEEK2_PLAN §6). Standard library only.

Logs in as a seed student, submits the A+B reference solution, waits for the verdict and checks
that the points show up in the problems list. Run from the repo root after
`docker compose up -d --build --wait`:

    python scripts/smoke_test.py

Env: SMOKE_API_URL (default http://localhost:8000/api), SMOKE_USERNAME, SMOKE_PASSWORD.
Exit code 0 = pass.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_URL = os.environ.get("SMOKE_API_URL", "http://localhost:8000/api").rstrip("/")
USERNAME = os.environ.get("SMOKE_USERNAME", "student1")
PASSWORD = os.environ.get("SMOKE_PASSWORD", "123456")
CONTEST_CODE = "project120261"
PROBLEM_CODE = "P_ADD_SUB_MUL_DIV"
SOLUTION = Path("data/seed/problems") / PROBLEM_CODE / "solutions" / "ac.cpp"
HEALTH_TIMEOUT_S = 60
JUDGE_TIMEOUT_S = 60
POLL_INTERVAL_S = 1.0
REQUEST_TIMEOUT_S = 10
COOLDOWN_RETRY_S = 6  # SUBMIT_COOLDOWN_SECONDS (5) + 1
FINAL_STATUSES = {"AC", "WA", "TLE", "MLE", "RE", "CE", "PARTIAL", "SE"}


class SmokeFailure(Exception):
    pass


def request(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API_URL}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise SmokeFailure(f"{method} {path} -> {exc.code}: {exc.read().decode()}") from exc


def wait_for_health() -> None:
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    while True:
        try:
            if request("GET", "/health").get("status") == "ok":
                return
        except (SmokeFailure, OSError):
            pass
        if time.monotonic() > deadline:
            raise SmokeFailure(f"API not healthy after {HEALTH_TIMEOUT_S} s")
        time.sleep(POLL_INTERVAL_S)


def find_problem(token: str, contest_id: int) -> dict:
    query = urllib.parse.urlencode({"search": PROBLEM_CODE, "size": 100})
    items = request("GET", f"/contests/{contest_id}/problems?{query}", token)["items"]
    matches = [item for item in items if item["code"] == PROBLEM_CODE]
    if not matches:
        raise SmokeFailure(f"problem {PROBLEM_CODE} not found in contest {contest_id}")
    return matches[0]


def wait_for_verdict(token: str, submission_id: int) -> dict:
    deadline = time.monotonic() + JUDGE_TIMEOUT_S
    while True:
        submission = request("GET", f"/submissions/{submission_id}", token)
        if submission["status"] in FINAL_STATUSES:
            return submission
        if time.monotonic() > deadline:
            raise SmokeFailure(
                f"submission {submission_id} still {submission['status']} after "
                f"{JUDGE_TIMEOUT_S} s — is a judge (or scripts.fake_judge) running?"
            )
        time.sleep(POLL_INTERVAL_S)


def run() -> str:
    wait_for_health()
    token = request("POST", "/auth/login", body={"username": USERNAME, "password": PASSWORD})[
        "token"
    ]

    contests = request("GET", "/contests?size=100", token)["items"]
    contest = next((c for c in contests if c["code"] == CONTEST_CODE), None)
    if contest is None:
        raise SmokeFailure(f"contest {CONTEST_CODE} not found (is SEED_ON_START=true?)")

    problem = find_problem(token, contest["id"])
    source = SOLUTION.read_text(encoding="utf-8")
    submit_path = f"/contests/{contest['id']}/problems/{problem['id']}/submit"
    body = {"language": "cpp17", "source_code": source}
    try:
        submitted = request("POST", submit_path, token, body)
    except SmokeFailure as exc:
        if "RATE_LIMITED" not in str(exc):
            raise
        time.sleep(COOLDOWN_RETRY_S)  # a previous run submitted moments ago
        submitted = request("POST", submit_path, token, body)

    submission = wait_for_verdict(token, submitted["submission_id"])
    if submission["status"] != "AC" or submission["score"] != problem["max_points"]:
        raise SmokeFailure(
            f"expected AC {problem['max_points']}, got {submission['status']} "
            f"{submission['score']}: {submission.get('compile_output') or ''}"
        )

    after = find_problem(token, contest["id"])
    if after["points_earned"] != after["max_points"] or not after["is_complete"]:
        raise SmokeFailure(f"problems list not updated: {after}")
    return (
        f"submission {submission['id']} AC {submission['score']}/{problem['max_points']}, "
        f"problems list shows {after['points_earned']}/{after['max_points']} complete"
    )


def main() -> int:
    if not SOLUTION.is_file():
        sys.stderr.write(f"SMOKE FAIL: {SOLUTION} not found — run from the repo root\n")
        return 1
    try:
        summary = run()
    except SmokeFailure as exc:
        sys.stderr.write(f"SMOKE FAIL: {exc}\n")
        return 1
    sys.stdout.write(f"SMOKE PASS: {summary}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
