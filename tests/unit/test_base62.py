"""Tests for base62 encoding (alphabet order: 0-9, a-z, A-Z)."""

import pytest
from app.base62 import encode


def test_matches_the_worked_example_from_system_design_interview():
    # 11157 = 2*62^2 + 55*62 + 59, i.e. digits [2, 55, 59] -> "2", "T", "X".
    assert encode(11157) == "2TX"


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (0, "0"),  # smallest value
        (9, "9"),  # last digit
        (10, "a"),  # first lowercase letter
        (35, "z"),  # last lowercase letter
        (36, "A"),  # first uppercase letter
        (61, "Z"),  # highest single character
        (62, "10"),  # carry into a second character
    ],
)
def test_boundaries(number, expected):
    assert encode(number) == expected


def test_negative_numbers_are_rejected():
    with pytest.raises(ValueError):
        encode(-1)
