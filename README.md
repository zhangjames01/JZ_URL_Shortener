# URL Shortener API

A REST API that turns a long URL into a short link, redirects visitors to the original, and reports
metadata and click statistics for every link. Built with Python 3.12 and FastAPI, developed
test-first, and deployable to DigitalOcean.

[![CI](https://github.com/zhangjames01/JZ_URL_Shortener/actions/workflows/ci.yml/badge.svg)](https://github.com/zhangjames01/JZ_URL_Shortener/actions/workflows/ci.yml)

## Features

- **Create** a short link from a long URL, with an auto-generated 7-character code.
- **Custom aliases** with validation (letters and digits, 3 to 32 characters, reserved words blocked).
- **Redirect** with a `302`, counting every visit.
- **Metadata and statistics** for any link: creation time, click count, last visit.
- **One consistent error format** for every failure, with stable machine-readable codes.
- **Two storage backends** behind one interface: SQLite for local work, PostgreSQL in production.

Documentation: [architecture and design decisions](docs/architecture.md) (with request-lifecycle and
deployment diagrams) and the [deployment guide](docs/deployment.md).

## Quick start

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the server (uses a local SQLite file, `urls.db`):

```bash
uvicorn app.main:create_app --factory --reload
```

Try it. Interactive API docs are also served at <http://localhost:8000/docs>.

```bash
curl -s -X POST localhost:8000/api/v1/urls \
  -H 'content-type: application/json' \
  -d '{"url": "https://example.com/some/very/long/page", "alias": "demo"}'
```

```bash
curl -i localhost:8000/demo
```

```bash
curl -s localhost:8000/api/v1/urls/demo
```

### Run with Docker

```bash
docker build -t url-shortener .
docker run -p 8080:8080 -e BASE_URL=http://localhost:8080 url-shortener
```

Without `DATABASE_URL` the container keeps its SQLite file inside itself, so data is lost when the
container is replaced. Set `DATABASE_URL` to a PostgreSQL connection string for persistence.

## API

All request and response bodies are JSON.

### Create a short link

`POST /api/v1/urls`

| Field | Type | Required | Notes |
|---|---|---|---|
| `url` | string | yes | `http` or `https`, must have a host, at most 2048 characters, no whitespace or embedded credentials |
| `alias` | string or null | no | 3 to 32 letters or digits, case-sensitive. Omit or send `null` to generate a code |

`201 Created`:

```json
{
  "code": "demo",
  "short_url": "http://localhost:8000/demo",
  "original_url": "https://example.com/some/very/long/page",
  "created_at": "2026-01-01T12:00:00Z",
  "click_count": 0,
  "last_accessed_at": null
}
```

Without an alias, `code` is a generated 7-character value such as `1000000`.

### Follow a short link

`GET /{code}` responds `302 Found` with a `Location` header holding the original URL, and counts one
click. A failure to record the click is logged but never blocks the redirect.

### Get link metadata

`GET /api/v1/urls/{code}` returns `200` with the same fields as the create response. Reading
metadata does **not** count as a click.

### Health check

`GET /healthz` returns `{"status": "ok"}`.

### Errors

Every error uses the same shape:

```json
{"error": {"code": "ALIAS_TAKEN", "message": "Alias 'demo' is already in use"}}
```

| HTTP status | `error.code` | When |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Malformed request: missing field, wrong type, invalid JSON |
| 422 | `INVALID_URL` | The URL breaks a validation rule |
| 422 | `INVALID_ALIAS` | Wrong characters or length, or a reserved word (`api`, `healthz`, `docs`, `redoc`) |
| 409 | `ALIAS_TAKEN` | The requested alias already exists. There is no silent fallback to a generated code |
| 404 | `NOT_FOUND` | Unknown short code or path |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method for the path |
| 500 | `INTERNAL_ERROR` | Unexpected failure. The message is generic and details are only logged |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `BASE_URL` | `http://localhost:8000` | Public address used to build `short_url` |
| `DATABASE_PATH` | `urls.db` | SQLite file, used when `DATABASE_URL` is not set |
| `DATABASE_URL` | not set | PostgreSQL connection string. When set, PostgreSQL is used instead of SQLite |
| `PORT` | `8080` | Port inside the Docker image |

## Testing

```bash
pytest
```

143 tests: 112 unit and 31 integration. The Postgres cases are skipped unless a test database is
configured. To run everything, start a disposable Postgres and point the tests at it:

```bash
docker run -d --name url-shortener-test-pg -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=url_shortener_test -p 5433:5432 postgres:17
```

```bash
TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/url_shortener_test pytest
```

The tests **drop tables**, so they refuse to run against any database whose name does not contain
`test`. Lint and formatting (as CI runs them; `--no-cache` avoids a stale cache hiding import-order
problems):

```bash
ruff check --no-cache . && ruff format --no-cache --check .
```

## How this was built: test-driven development

Every feature followed the same loop, and the tests were treated as the specification, not an
afterthought:

1. **Decide before coding.** Requirements and design choices were agreed first, with the alternatives
   and trade-offs written down (see [design decisions](docs/architecture.md#design-decisions)).
2. **Write the tests first and explain them.** Each test states what behaviour it pins down and why.
3. **Watch them fail for the right reason** before writing any implementation.
4. **Implement the minimum** to make them pass, then refactor with the tests as a safety net.
5. **Break the code on purpose.** After going green, the implementation was deliberately mutated
   (for example making a lookup case-insensitive, or making a click increment non-atomic) to prove
   the tests actually catch the bug.

What that habit produced:

- **Weak tests found and fixed.** Mutation checks exposed three tests that passed while proving
  nothing: a case-sensitivity test (it now also asserts the exact-case link works), a UTC test that
  passed only because the test database was already in UTC (it now forces a non-UTC session), and a
  route-discovery guard that silently skipped the API routes (it now uses public interfaces and
  asserts it found the routes it expects).
- **One contract suite, two backends.** The repository tests run once per backend (SQLite and
  PostgreSQL), so both must behave identically. This is what made adding PostgreSQL a change to one
  new file, with no edits to the service, routes or validation.
- **Tests that guard the tests.** CI sets `REQUIRE_POSTGRES=1`, so a missing database service fails the
  build instead of quietly skipping the Postgres tests.
- **Concurrency is tested, not assumed.** Parallel `next_id` and `record_click` calls prove that codes
  stay unique and no click is lost.
- **Tests as executable examples.** The base62 tests reproduce the worked example from *System Design
  Interview* (11157 encodes to `2TX`).

## Project layout

```
app/
  main.py                   application wiring, backend selection, shutdown
  config.py                 settings from environment variables
  schemas.py                request and response bodies
  service.py                business rules: create, visit, get_link
  validation.py             URL and alias rules (pure functions)
  codegen.py, base62.py     turning a counter into a short code
  repository.py             UrlRepository interface and the SQLite implementation
  postgres_repository.py    PostgreSQL implementation
  errors.py                 domain exceptions (no HTTP details)
  api/routes.py             thin HTTP layer
  api/error_handlers.py     maps errors to the JSON error format
tests/
  unit/                     rules, service, repository contract, configuration
  integration/              HTTP behaviour through the real app
docs/                       architecture.md, deployment.md
.do/app.yaml                DigitalOcean App Platform spec
.github/workflows/ci.yml    lint, format check and tests against Postgres 17
Dockerfile
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request:
`ruff check`, `ruff format --check`, then `pytest` against a real PostgreSQL 17 service container.

Deployment to DigitalOcean App Platform is described in [docs/deployment.md](docs/deployment.md) and
configured in [`.do/app.yaml`](.do/app.yaml). The spec was written from DigitalOcean's documentation
and could not be validated without an account token, so treat the first real deploy as its test.
The app is set to redeploy on every push to `main`; that does not wait for CI.

## Known limitations

- **Codes are sequential, so they are guessable.** This is the trade-off of encoding a counter. It
  guarantees uniqueness, but anyone can enumerate links. Permuting the counter before encoding would
  hide the order.
- **No authentication, ownership or rate limiting.** Anyone can create links.
- **`HEAD` requests to a short link return 405.** Link-preview crawlers that use `HEAD` will not work.
- **A click is every successful redirect.** There is no unique-visitor tracking, bot filtering or
  referrer data.
- **No expiry, editing or deletion of links.**
- **No migrations.** Tables are created at startup with `IF NOT EXISTS`. Use a migration tool before
  changing the schema under real data.
- **Development database.** The deployment spec uses a single-node dev database without backups.
  Use a managed cluster (`production: true`) for a real launch.
- **SQLite is for local use.** It has one connection and a lock, and on App Platform its file is lost on
  every redeploy.
