"""Tests for turning a sequential counter value into a short code."""

from app.codegen import code_for_id


def test_first_code_is_seven_characters_long():
    # Codes start at 62**6 so every generated code has exactly 7 characters.
    assert code_for_id(1) == "1000000"


def test_codes_follow_the_counter():
    assert code_for_id(2) == "1000001"
    assert code_for_id(63) == "1000010"  # carries into the next character
