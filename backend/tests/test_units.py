"""Pure helpers: no DB needed."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.pagination import PageParams
from app.schemas import _to_utc_iso
from app.services.problems import _like_pattern
from app.services.testcase_storage import SAMPLE_MAX_BYTES, read_sample_file, resolve_inside


def test_page_offset() -> None:
    assert PageParams(page=1, size=5).offset == 0
    assert PageParams(page=3, size=10).offset == 20


def test_like_pattern_escapes_wildcards() -> None:
    assert _like_pattern("a%b_c\\d") == "%a\\%b\\_c\\\\d%"


def test_utc_iso_uses_z_suffix_and_whole_seconds() -> None:
    value = datetime(2026, 11, 20, 9, 49, 0, 123456, tzinfo=UTC)

    assert _to_utc_iso(value) == "2026-11-20T09:49:00Z"


def test_utc_iso_converts_other_timezones() -> None:
    hanoi = timezone(timedelta(hours=7))

    assert _to_utc_iso(datetime(2026, 11, 20, 16, 49, tzinfo=hanoi)) == "2026-11-20T09:49:00Z"


def test_utc_iso_treats_naive_as_utc() -> None:
    assert _to_utc_iso(datetime(2026, 11, 20, 9, 49)) == "2026-11-20T09:49:00Z"


def test_resolve_inside_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_inside(tmp_path, "../secret.txt")


def test_read_sample_file_caps_size(tmp_path: Path) -> None:
    (tmp_path / "big.in").write_bytes(b"x" * (SAMPLE_MAX_BYTES + 100))

    assert len(read_sample_file(tmp_path, "big.in")) == SAMPLE_MAX_BYTES


def test_read_sample_file_returns_none_when_missing(tmp_path: Path) -> None:
    assert read_sample_file(tmp_path, "missing.in") is None


def test_read_sample_file_returns_none_on_escape(tmp_path: Path) -> None:
    assert read_sample_file(tmp_path, "../../etc/passwd") is None
