from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from main import SPACES_DIR, build_view_name, collect_sql_files  # noqa: E402

_VIEW_NAME_RE = re.compile(r"^holmes_[a-z0-9_]+_view$")


@pytest.fixture(params=collect_sql_files(), ids=lambda t: t[1])
def sql_file_and_view(request):
    return request.param


def test_build_view_name():
    p = SPACES_DIR / "sherlock" / "ccm_data.sql"
    assert build_view_name(p) == "holmes_sherlock_ccm_data_view"


def test_view_name_format(sql_file_and_view):
    _, view_name = sql_file_and_view
    assert _VIEW_NAME_RE.match(view_name)


def test_sql_file_not_empty(sql_file_and_view):
    sql_path, _ = sql_file_and_view
    assert sql_path.stat().st_size > 0


def test_sql_starts_with_select_or_with(sql_file_and_view):
    sql_path, _ = sql_file_and_view
    content = sql_path.read_text(encoding="utf-8").lstrip()
    assert content.upper().startswith(("SELECT", "WITH"))


def test_directory_depth():
    for sql_path, _ in collect_sql_files():
        depth = len(sql_path.relative_to(SPACES_DIR).parts) - 1
        assert depth == 1


def test_view_name_uniqueness():
    files = collect_sql_files()
    names = [v for _, v in files]
    duplicates = {v for v in names if names.count(v) > 1}
    assert not duplicates
