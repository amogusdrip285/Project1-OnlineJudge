"""Output normalization and comparison rules (MASTER_PLAN §7.3)."""


def normalize_output(text: str) -> str:
    """Normalize CRLF line endings, trailing spaces/tabs per line, and trailing empty lines."""
    lines = [line.rstrip(" \t") for line in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def outputs_match(actual: str, expected: str) -> bool:
    """Return True when actual program output matches expected output per judge rules."""
    return normalize_output(actual) == normalize_output(expected)
