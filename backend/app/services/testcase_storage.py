"""Reading testcase files under PROBLEMS_DIR (MASTER_PLAN §5)."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_MAX_BYTES = 4096


def resolve_inside(base_dir: str | Path, relative_path: str) -> Path:
    """Join and refuse any path that escapes `base_dir` (e.g. `../../etc/passwd`)."""
    base = Path(base_dir).resolve()
    target = (base / relative_path).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"path escapes the problems directory: {relative_path}")
    return target


def read_sample_file(base_dir: str | Path, relative_path: str) -> str | None:
    """First 4 KB of a testcase file as text, or None (logged) if it can't be read."""
    try:
        path = resolve_inside(base_dir, relative_path)
        with path.open("rb") as handle:
            data = handle.read(SAMPLE_MAX_BYTES)
    except (OSError, ValueError) as exc:
        logger.warning("Cannot read sample testcase %s: %s", relative_path, exc)
        return None
    return data.decode("utf-8", errors="replace")
