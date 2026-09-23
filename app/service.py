"""Business logic for creating short links.

The service owns the rules (validate, generate a code, handle collisions). It talks to
storage only through the `UrlRepository` interface and knows nothing about HTTP.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from app.codegen import code_for_id
from app.errors import AliasTakenError, CodeGenerationError, DuplicateCodeError
from app.repository import UrlRecord, UrlRepository
from app.validation import validate_alias, validate_long_url

# How many counter values to try before giving up. A generated code can only collide
# with a code someone claimed earlier (e.g. a custom alias), so needing more than a
# couple of attempts is very unusual; the cap prevents an endless loop if it happens.
MAX_CODE_ATTEMPTS = 5


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ShortenerService:
    def __init__(
        self,
        repository: UrlRepository,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._repository = repository
        # Injected so tests can use a fixed time instead of the real clock.
        self._clock = clock

    def create(self, url: str, alias: str | None = None) -> UrlRecord:
        """Store `url` under `alias` if given, otherwise under a generated code.

        Everything is validated before anything is written. If both inputs are
        invalid, the URL error is reported first.
        """
        original_url = validate_long_url(url)
        if alias is not None:
            validate_alias(alias)
            return self._create_custom(original_url, alias)
        return self._create_generated(original_url)

    def _create_custom(self, original_url: str, alias: str) -> UrlRecord:
        record = UrlRecord(code=alias, original_url=original_url, created_at=self._clock())
        try:
            # The database's PRIMARY KEY decides races: no check-then-insert gap.
            self._repository.add(record)
        except DuplicateCodeError as exc:
            raise AliasTakenError(alias) from exc
        return record

    def _create_generated(self, original_url: str) -> UrlRecord:
        for _ in range(MAX_CODE_ATTEMPTS):
            code = code_for_id(self._repository.next_id())
            record = UrlRecord(code=code, original_url=original_url, created_at=self._clock())
            try:
                self._repository.add(record)
            except DuplicateCodeError:
                # The code was already taken (e.g. claimed earlier as a custom alias);
                # move on to the next counter value.
                continue
            return record

        raise CodeGenerationError(f"no free short code after {MAX_CODE_ATTEMPTS} attempts")
