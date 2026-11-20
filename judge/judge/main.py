"""PLACEHOLDER worker (Person A, Day 0). Person B replaces this with the real judge loop
(MASTER_PLAN §7). It only logs and idles so `docker compose up` works on Day 0."""

import logging
import time

IDLE_SECONDS = 60


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("judge placeholder started: waiting for jobs (real judge not implemented yet)")
    while True:
        time.sleep(IDLE_SECONDS)


if __name__ == "__main__":
    main()
