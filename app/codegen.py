"""Short-code generation from a sequential counter."""

from app.base62 import BASE, encode

# Starting the sequence at 62**6 makes every generated code exactly 7 characters long
# (62**7, about 3.5 trillion codes, before the length would grow). Codes are still
# sequential and therefore guessable; that is a documented trade-off of this scheme.
FIRST_CODE_VALUE = BASE**6


def code_for_id(counter: int) -> str:
    """Map counter value 1, 2, 3... to the codes "1000000", "1000001", ..."""
    return encode(FIRST_CODE_VALUE + counter - 1)
