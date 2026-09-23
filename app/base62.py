"""Base62 encoding: turns a non-negative integer into a compact string.

Alphabet order is 0-9, a-z, A-Z (so 10 -> "a" and 36 -> "A"). This is the scheme
described in "System Design Interview" for building short URLs from unique ids.
"""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)


def encode(number: int) -> str:
    if number < 0:
        raise ValueError("number must be non-negative")
    if number == 0:
        return ALPHABET[0]

    # Repeatedly divide by 62; each remainder is one character, least significant first.
    digits = []
    while number:
        number, remainder = divmod(number, BASE)
        digits.append(ALPHABET[remainder])
    return "".join(reversed(digits))
