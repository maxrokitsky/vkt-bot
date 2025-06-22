FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

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

ENTRYPOINT []

CMD ["uv", "run", "bot"]
