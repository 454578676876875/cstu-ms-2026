import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "assignment"))

import select_tests as st


def test_selects_only_the_matching_test_file():
    tests, is_full = st.select_tests_for_changed_files(["app/math_ops.py"])
    assert not is_full
    assert [t.name for t in tests] == ["test_math_ops.py"]


def test_multiple_changed_files_selects_multiple_tests():
    tests, is_full = st.select_tests_for_changed_files(["app/math_ops.py", "app/string_ops.py"])
    assert not is_full
    assert {t.name for t in tests} == {"test_math_ops.py", "test_string_ops.py"}


def test_shared_file_change_falls_back_to_full_suite():
    tests, is_full = st.select_tests_for_changed_files(["conftest.py"])
    assert is_full
    assert len(tests) == 3


def test_unknown_app_file_falls_back_to_full_suite():
    tests, is_full = st.select_tests_for_changed_files(["app/does_not_exist.py"])
    assert is_full
