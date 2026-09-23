"""Tests for custom alias validation rules."""

import pytest

from app.errors import InvalidAliasError
from app.validation import MAX_ALIAS_LENGTH, MIN_ALIAS_LENGTH, validate_alias


@pytest.mark.parametrize(
    "alias",
    [
        "promo",
        "Promo123",  # mixed case is allowed; aliases are case-sensitive
        "12345",  # digits only
        "a" * MIN_ALIAS_LENGTH,  # exactly at the minimum
        "a" * MAX_ALIAS_LENGTH,  # exactly at the maximum
    ],
)
def test_accepts_valid_aliases(alias):
    assert validate_alias(alias) == alias


@pytest.mark.parametrize(
    "alias",
    [
        "",  # empty
        "a" * (MIN_ALIAS_LENGTH - 1),  # one under the minimum
        "a" * (MAX_ALIAS_LENGTH + 1),  # one over the maximum
        "my-link",  # only letters and digits are allowed
        "my_link",
        "my link",
        "a/b",  # would look like a nested path
        "../x",
        "café",  # str.isalnum() would accept this; we allow ASCII only
        "promo\n",  # a regex "$" would tolerate the trailing newline; fullmatch must not
        " promo ",  # aliases are not trimmed: reject instead of silently changing them
    ],
)
def test_rejects_aliases_with_bad_length_or_characters(alias):
    with pytest.raises(InvalidAliasError):
        validate_alias(alias)


@pytest.mark.parametrize("alias", ["api", "healthz", "docs", "redoc", "API", "Docs"])
def test_rejects_reserved_aliases_in_any_letter_case(alias):
    # These would collide with (or impersonate) the service's own routes, so the
    # comparison ignores case even though aliases are otherwise case-sensitive.
    with pytest.raises(InvalidAliasError):
        validate_alias(alias)
