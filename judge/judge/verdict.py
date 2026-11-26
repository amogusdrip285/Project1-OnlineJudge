"""Per-test verdict and submission score aggregation rules (MASTER_PLAN §7.2)."""

from collections.abc import Sequence
from dataclasses import dataclass

from judge.compare import outputs_match

TEST_VERDICTS = ("AC", "WA", "TLE", "MLE", "RE")
FINAL_STATUSES = ("AC", "WA", "TLE", "MLE", "RE", "CE", "PARTIAL", "SE")
MAX_COMPILE_OUTPUT_BYTES = 10 * 1024


@dataclass(frozen=True)
class TestOutcome:
    """Result for a single testcase execution."""

    testcase_id: int
    verdict: str
    time_ms: int
    memory_kb: int


@dataclass(frozen=True)
class SubmissionVerdict:
    """Aggregated submission verdict and metrics ready to persist to DB."""

    status: str
    score: int
    tests_passed: int
    tests_total: int
    time_ms: int | None
    memory_kb: int | None
    compile_output: str | None


def truncate_compile_output(
    stderr: str | None, max_bytes: int = MAX_COMPILE_OUTPUT_BYTES
) -> str | None:
    """Cap compiler stderr at max_bytes UTF-8 bytes without splitting multibyte chars."""
    if stderr is None:
        return None
    encoded = stderr.encode("utf-8")
    if len(encoded) <= max_bytes:
        return stderr
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def decide_test_verdict(
    *,
    timed_out: bool,
    memory_exceeded: bool,
    exit_code: int | None,
    signal_num: int | None,
    actual_output: str,
    expected_output: str,
    output_truncated: bool = False,
) -> str:
    """Determine single-test verdict in priority order: TLE -> MLE -> RE -> AC/WA."""
    if timed_out:
        return "TLE"
    if memory_exceeded:
        return "MLE"
    if signal_num is not None or (exit_code is not None and exit_code != 0):
        return "RE"
    if output_truncated:
        return "WA"
    return "AC" if outputs_match(actual_output, expected_output) else "WA"


def aggregate_submission(
    *,
    max_points: int,
    outcomes: Sequence[TestOutcome],
    compile_failed: bool = False,
    compile_output: str | None = None,
    system_error: bool = False,
) -> SubmissionVerdict:
    """Compute final submission status, partial score, and max time/memory."""
    if system_error:
        return SubmissionVerdict(
            status="SE",
            score=0,
            tests_passed=0,
            tests_total=len(outcomes),
            time_ms=None,
            memory_kb=None,
            compile_output=None,
        )

    if compile_failed:
        return SubmissionVerdict(
            status="CE",
            score=0,
            tests_passed=0,
            tests_total=0,
            time_ms=None,
            memory_kb=None,
            compile_output=truncate_compile_output(compile_output),
        )

    tests_total = len(outcomes)
    if tests_total == 0:
        return SubmissionVerdict(
            status="SE",
            score=0,
            tests_passed=0,
            tests_total=0,
            time_ms=None,
            memory_kb=None,
            compile_output=None,
        )

    for outcome in outcomes:
        if outcome.verdict not in TEST_VERDICTS:
            raise ValueError(f"Invalid testcase verdict: {outcome.verdict}")

    tests_passed = sum(1 for outcome in outcomes if outcome.verdict == "AC")
    score = (max_points * tests_passed) // tests_total
    max_time_ms = max(outcome.time_ms for outcome in outcomes)
    max_memory_kb = max(outcome.memory_kb for outcome in outcomes)

    if tests_passed == tests_total:
        status = "AC"
    elif tests_passed >= 1:
        status = "PARTIAL"
    else:
        status = outcomes[0].verdict

    return SubmissionVerdict(
        status=status,
        score=score,
        tests_passed=tests_passed,
        tests_total=tests_total,
        time_ms=max_time_ms,
        memory_kb=max_memory_kb,
        compile_output=None,
    )
