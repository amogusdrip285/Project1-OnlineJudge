"""Stand-in judge for demos and frontend work: marks every PENDING submission as AC.

Claims jobs with the same SQL as the real judge (MASTER_PLAN §7.1). NEVER run it while the real
judge container is running: both would claim jobs.

    python -m scripts.fake_judge            # loop forever
    python -m scripts.fake_judge --once     # judge at most one submission, then exit
"""

import argparse
import logging
import time

from sqlalchemy import Connection, text

from app.db import engine

logger = logging.getLogger("fake_judge")

POLL_SECONDS = 0.5
FAKE_JUDGING_SECONDS = 1.0
FAKE_TIME_MS = 1
FAKE_MEMORY_KB = 1024
STALE_AFTER_SECONDS = 120  # same default as JUDGE_STALE_AFTER_SECONDS

CLAIM_SQL = text(
    """
    UPDATE submissions
    SET status = 'JUDGING', judging_started_at = now()
    WHERE id = (
      SELECT id FROM submissions
      WHERE status = 'PENDING'
      ORDER BY id
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    )
    RETURNING id, problem_id, max_points
    """
)
TESTCASES_SQL = text("SELECT id FROM testcases WHERE problem_id = :problem_id ORDER BY order_index")
INSERT_RESULT_SQL = text(
    """
    INSERT INTO submission_results (submission_id, testcase_id, verdict, time_ms, memory_kb)
    VALUES (:submission_id, :testcase_id, 'AC', :time_ms, :memory_kb)
    """
)
FINISH_SQL = text(
    """
    UPDATE submissions
    SET status = :status, score = :score, tests_passed = :total, tests_total = :total,
        time_ms = :time_ms, memory_kb = :memory_kb, judged_at = now()
    WHERE id = :id AND status = 'JUDGING'
    """
)

MARK_SE_SQL = text(
    """
    UPDATE submissions SET status = 'SE', score = 0, judged_at = now()
    WHERE id = :id AND status = 'JUDGING'
    """
)
RESET_STALE_SQL = text(
    """
    UPDATE submissions SET status = 'PENDING', judging_started_at = NULL
    WHERE status = 'JUDGING' AND judging_started_at < now() - make_interval(secs => :seconds)
    """
)


class LostJobError(Exception):
    """The job is no longer JUDGING (e.g. stale recovery gave it back to the queue)."""


def claim(connection: Connection) -> tuple[int, int, int] | None:
    """(submission_id, problem_id, max_points) of the claimed job, or None if the queue is empty."""
    row = connection.execute(CLAIM_SQL).first()
    return (row.id, row.problem_id, row.max_points) if row else None


def finish_as_accepted(
    connection: Connection, submission_id: int, problem_id: int, max_points: int
) -> str:
    """Write an AC result (or SE when the problem has no testcases). Returns the status."""
    testcase_ids = connection.execute(TESTCASES_SQL, {"problem_id": problem_id}).scalars().all()
    for testcase_id in testcase_ids:
        connection.execute(
            INSERT_RESULT_SQL,
            {
                "submission_id": submission_id,
                "testcase_id": testcase_id,
                "time_ms": FAKE_TIME_MS,
                "memory_kb": FAKE_MEMORY_KB,
            },
        )
    status = "AC" if testcase_ids else "SE"
    updated = connection.execute(
        FINISH_SQL,
        {
            "id": submission_id,
            "status": status,
            "score": max_points if testcase_ids else 0,
            "total": len(testcase_ids),
            "time_ms": FAKE_TIME_MS if testcase_ids else None,
            "memory_kb": FAKE_MEMORY_KB if testcase_ids else None,
        },
    )
    if updated.rowcount == 0:
        # Raising rolls back the result rows inserted above.
        raise LostJobError(f"submission {submission_id} is no longer JUDGING")
    return status


def reset_stale(connection: Connection, seconds: int = STALE_AFTER_SECONDS) -> int:
    """Give jobs stuck in JUDGING (a crashed judge) back to the queue. Returns how many."""
    return connection.execute(RESET_STALE_SQL, {"seconds": seconds}).rowcount


def judge_one(delay_seconds: float = FAKE_JUDGING_SECONDS) -> int | None:
    """Claim and finish one job in two transactions, like the real judge. Returns its id."""
    with engine.begin() as connection:
        job = claim(connection)
    if job is None:
        return None
    time.sleep(delay_seconds)
    try:
        with engine.begin() as connection:
            status = finish_as_accepted(connection, *job)
    except LostJobError as exc:
        logger.warning("%s", exc)
        return job[0]
    except Exception:
        logger.exception("submission %s failed; marking SE", job[0])
        with engine.begin() as connection:
            connection.execute(MARK_SE_SQL, {"id": job[0]})
        return job[0]
    logger.info("submission %s -> %s", job[0], status)
    return job[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true", help="judge at most one submission")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.warning("FAKE judge: every submission becomes AC. Do not run with the real judge.")
    with engine.begin() as connection:
        reset = reset_stale(connection)
    if reset:
        logger.info("reset %s stale JUDGING submission(s) to PENDING", reset)
    if args.once:
        judge_one()
        return
    while True:
        try:
            idle = judge_one() is None
        except Exception:  # e.g. DB restarting: keep the worker alive
            logger.exception("fake judge loop error")
            idle = True
        if idle:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
