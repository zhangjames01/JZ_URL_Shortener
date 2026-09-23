"""Domain-level exceptions.

These are raised by the storage and service layers and carry no HTTP details. The API
layer is responsible for translating them into HTTP responses, so lower layers stay
independent of the web framework.
"""


class DuplicateCodeError(Exception):
    """Raised when a short code is already in use."""
