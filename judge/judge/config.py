"""Judge worker configuration read from environment variables (MASTER_PLAN §3.2)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class JudgeSettings:
    """Immutable settings for the judge worker."""

    database_url: str = "postgresql://oj:change-me@127.0.0.1:5432/oj"
    problems_dir: str = "/data/problems"
    poll_interval_ms: int = 500
    stale_after_seconds: int = 120
    compile_timeout_seconds: int = 10
    max_output_bytes: int = 16_777_216
    compile_output_max_bytes: int = 10_240


def _parse_positive_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{key} must be a positive integer, got {value}")
    return value


def load_settings(environ: Mapping[str, str] | None = None) -> JudgeSettings:
    """Load judge settings from environment variables."""
    env = os.environ if environ is None else environ
    return JudgeSettings(
        database_url=env.get("DATABASE_URL") or JudgeSettings.database_url,
        problems_dir=env.get("PROBLEMS_DIR") or JudgeSettings.problems_dir,
        poll_interval_ms=_parse_positive_int(
            env, "JUDGE_POLL_INTERVAL_MS", JudgeSettings.poll_interval_ms
        ),
        stale_after_seconds=_parse_positive_int(
            env, "JUDGE_STALE_AFTER_SECONDS", JudgeSettings.stale_after_seconds
        ),
        compile_timeout_seconds=_parse_positive_int(
            env, "JUDGE_COMPILE_TIMEOUT_SECONDS", JudgeSettings.compile_timeout_seconds
        ),
        max_output_bytes=_parse_positive_int(
            env, "JUDGE_MAX_OUTPUT_BYTES", JudgeSettings.max_output_bytes
        ),
    )
