"""Business rules for what counts as an acceptable long URL.

Kept as a pure function (no web framework, no I/O) so the rules are easy to unit test
and reuse. The request schema only checks that the field is a string; this module
decides whether that string is acceptable.
"""

import re
from urllib.parse import urlsplit

from app.errors import InvalidAliasError, InvalidUrlError

# Practical upper bound for URLs; also limits how much a single request can store.
MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = {"http", "https"}


def validate_long_url(url: str) -> str:
    """Return the URL trimmed of surrounding whitespace, or raise InvalidUrlError.

    The URL is stored exactly as sent (after trimming); it is not normalised.
    """
    url = url.strip()
    if not url:
        raise InvalidUrlError("URL must not be empty")
    if len(url) > MAX_URL_LENGTH:
        raise InvalidUrlError(f"URL must be at most {MAX_URL_LENGTH} characters")

    # Whitespace or control characters (e.g. a newline) inside the URL could corrupt
    # the Location header we later send on redirect (header injection).
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url):
        raise InvalidUrlError("URL must not contain whitespace or control characters")

    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - accessing it validates the port; may raise ValueError
    except ValueError as exc:
        raise InvalidUrlError("URL is malformed") from exc

    # Only web links: schemes like javascript:, data: and file: are dangerous targets.
    if parts.scheme not in ALLOWED_SCHEMES:
        raise InvalidUrlError("URL must start with http:// or https://")
    if not parts.hostname:
        raise InvalidUrlError("URL must include a host")

    # "https://google.com@evil.com" really points at evil.com; reject embedded
    # credentials because they are a common phishing disguise.
    if parts.username is not None or parts.password is not None:
        raise InvalidUrlError("URL must not contain credentials")

    return url


MIN_ALIAS_LENGTH = 3
MAX_ALIAS_LENGTH = 32

# ASCII letters and digits only. `str.isalnum()` is avoided on purpose because it also
# accepts accented and non-Latin characters.
_ALIAS_PATTERN = re.compile(rf"[A-Za-z0-9]{{{MIN_ALIAS_LENGTH},{MAX_ALIAS_LENGTH}}}")

# Aliases are served from the site root (/{alias}), so they must not shadow the
# service's own top-level routes. If you add a new root-level route, add its first path
# segment here; tests/integration/test_reserved_aliases.py fails if you forget.
RESERVED_ALIASES = frozenset({"api", "healthz", "docs", "redoc"})


def validate_alias(alias: str) -> str:
    """Return `alias` unchanged if it is acceptable, otherwise raise InvalidAliasError.

    Aliases are case-sensitive and are not trimmed: a value with stray spaces is
    rejected rather than silently altered.
    """
    # fullmatch (not match/$) so a trailing newline cannot slip through.
    if not _ALIAS_PATTERN.fullmatch(alias):
        raise InvalidAliasError(
            f"Alias must be {MIN_ALIAS_LENGTH}-{MAX_ALIAS_LENGTH} letters or digits (a-z, A-Z, 0-9)"
        )
    # Reserved words are compared ignoring case so "API" cannot pass as our own route.
    if alias.lower() in RESERVED_ALIASES:
        raise InvalidAliasError(f"Alias '{alias}' is reserved")
    return alias
