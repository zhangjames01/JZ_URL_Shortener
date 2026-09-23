"""Business rules for what counts as an acceptable long URL.

Kept as a pure function (no web framework, no I/O) so the rules are easy to unit test
and reuse. The request schema only checks that the field is a string; this module
decides whether that string is acceptable.
"""

from urllib.parse import urlsplit

from app.errors import InvalidUrlError

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
