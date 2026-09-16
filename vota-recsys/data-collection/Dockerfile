# Not used for the Week 1 crawl (that runs on the host under `uv` - see
# README.md). This image exists so the pipeline is reproducible on Linux/CI.
FROM python:3.13-slim

# UTF-8 everywhere. The pipeline writes Vietnamese to stdout, to log files and
# to Postgres; a cp1252/ascii default makes every one of those a crash.
ENV PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer first so edits to the pipeline do not re-resolve the lock.
COPY pyproject.toml uv.lock* .python-version ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY . .

# data/ is a volume mount at runtime; make sure the tree exists either way.
RUN mkdir -p data/raw data/reports data/seed data/manual logs

# No default command: every pipeline step is an explicit invocation.
#   docker compose run --rm collector uv run python -m cli report
ENTRYPOINT ["uv", "run"]
CMD ["python", "-m", "cli", "--help"]
