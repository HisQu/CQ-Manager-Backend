FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/src/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    AUTHENTICATION_SECRET="cq-manager-development-authentication-secret-change-me" \
    CORS_ALLOW_ORIGIN="*" \
    PORT=8000 \
    CONNECTION_STRING="sqlite+aiosqlite:///database/cq-database.sqlite" \
    SMPT_SERVER="" \
    SMPT_PORT="" \
    SMPT_SENDER="" \
    USE_SMPT=""

WORKDIR /usr/src/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

EXPOSE 8000

CMD ["sh", "-c", "litestar --app-dir src/app --app app:app run --host 0.0.0.0 --port ${PORT:-8000} --debug"]
