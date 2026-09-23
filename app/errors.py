"""Domain-level exceptions.

These are raised by the storage and service layers and carry no HTTP details. The API
layer is responsible for translating them into HTTP responses, so lower layers stay
independent of the web framework.
"""


class DuplicateCodeError(Exception):
    """Raised when a short code is already in use."""


class InvalidUrlError(Exception):
    """Raised when a long URL breaks one of the validation rules."""


class CodeGenerationError(Exception):
    """Raised when a free short code could not be found within the retry limit."""


class InvalidAliasError(Exception):
    """Raised when a custom alias breaks one of the alias rules."""


class AliasTakenError(Exception):
    """Raised when a requested custom alias is already in use."""
