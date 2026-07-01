FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself.
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

# --forwarded-allow-ips="*" makes uvicorn trust the Cloud Run proxy's X-Forwarded-Proto
# header, so it knows requests are HTTPS. Without it, uvicorn assumes http and FastAPI's
# trailing-slash redirects emit an http:// Location, which the browser blocks as mixed
# content. Safe behind Cloud Run: the managed proxy sets these headers and clients can't
# spoof them.
CMD ["sh", "-c", "uv run --no-dev alembic upgrade head && uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000 --forwarded-allow-ips='*'"]
