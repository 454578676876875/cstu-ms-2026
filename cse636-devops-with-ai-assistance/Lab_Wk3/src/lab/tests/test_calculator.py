import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calculator import add, multiply


def test_add():
    assert add(2, 3) == 5  # Passes against the current (fixed) calculator.py; failed against
    # the pre-remediation buggy version captured in transcripts/lab_declined.txt.


def test_multiply():
    assert multiply(3, 4) == 12
