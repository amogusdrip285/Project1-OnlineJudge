"""Allowed enum values (MASTER_PLAN §4.2, §7.2). Stored as TEXT + CHECK constraints."""

ROLES = ("student", "admin")
LEVELS = ("easy", "medium", "hard")
LANGUAGES = ("cpp17", "python3")
SUBMISSION_STATUSES = ("PENDING", "JUDGING", "AC", "WA", "TLE", "MLE", "RE", "CE", "PARTIAL", "SE")
TEST_VERDICTS = ("AC", "WA", "TLE", "MLE", "RE")


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """Build a CHECK expression like "role IN ('student','admin')" from trusted constants."""
    quoted = ",".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"
