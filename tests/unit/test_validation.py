"""Tests for long-URL validation rules."""

import pytest
from app.validation import MAX_URL_LENGTH, validate_long_url

from app.errors import InvalidUrlError

_PREFIX = "https://example.com/"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://example.com",
        "HTTPS://EXAMPLE.COM",  # scheme and host are case-insensitive
        "https://example.com/path/to/page",
        "https://example.com/search?q=python&page=2#results",
        "https://example.com:8080/admin",
        _PREFIX + "a" * (MAX_URL_LENGTH - len(_PREFIX)),  # exactly at the limit
    ],
)
def test_accepts_valid_urls(url):
    assert validate_long_url(url) == url


def test_trims_surrounding_whitespace_and_returns_the_trimmed_form():
    assert validate_long_url("  https://example.com/a \n") == "https://example.com/a"


@pytest.mark.parametrize(
    "url",
    [
        "",  # empty
        "   ",  # only whitespace
        "example.com",  # no scheme
        "ftp://example.com/file",  # scheme not allowed
        "javascript:alert(1)",  # dangerous scheme
        "data:text/html,hello",  # dangerous scheme
        "file:///etc/passwd",  # local file
        "https://",  # no host
        "https:///path",  # no host
        "https://exa mple.com",  # space inside
        "https://example.com/a\nb",  # newline could corrupt the Location header
        "https://example.com/a\tb",  # control character
        "https://user:pw@example.com",  # embedded credentials
        "https://google.com@evil.com",  # userinfo used to disguise the real host
        _PREFIX + "a" * (MAX_URL_LENGTH - len(_PREFIX) + 1),  # one over the limit
    ],
)
def test_rejects_invalid_urls(url):
    with pytest.raises(InvalidUrlError):
        validate_long_url(url)
