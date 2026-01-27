FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS backend

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_SYNC=1

RUN apt-get update && apt-get upgrade -y
RUN apt-get install make nano

COPY . /app

RUN uv sync --locked --no-dev --all-packages

ENV PATH="/app/.venv/bin:$PATH"

# FROM node:20-alpine AS frontend

# WORKDIR /app/control-panel-app

# COPY control-panel-app/package.json control-panel-app/pnpm-lock.yaml* ./
# RUN corepack enable pnpm && pnpm install --frozen-lockfile

# COPY control-panel-app/ .
# RUN pnpm build

# FROM backend

# COPY --from=frontend /app/control-panel-app/dist /app/static

ENTRYPOINT []

CMD ["uv", "run", "bot"]
