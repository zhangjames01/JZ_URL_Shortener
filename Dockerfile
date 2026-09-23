FROM python:3.12-slim

# No .pyc files, and logs go straight to stdout so the platform can collect them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies before copying the source, so this layer is cached and only
# rebuilt when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as an unprivileged user. /data holds the SQLite file when running without an
# external database.
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser

# PORT is set by most platforms; 8080 is the default for local runs.
ENV PORT=8080 \
    DATABASE_PATH=/data/urls.db
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/healthz')"

# Shell form so ${PORT} is expanded; `exec` makes uvicorn PID 1 so it receives signals.
CMD exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT}
