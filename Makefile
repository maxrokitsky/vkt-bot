.PHONY: start services migrate bot server worker scheduler export_schema generate_client

# Адрес Redis для локального запуска: в compose он проброшен на 16379.
# ``?=`` — чтобы можно было подменить из окружения; если адрес есть в
# ``.env``, honcho возьмёт оттуда (env-файл у него перекрывает окружение).
REDIS_URL ?= redis://localhost:16379/0

# Всё разом: инфраструктура, миграции и четыре процесса под honcho.
# ``--wait`` держит паузу до healthcheck'ов — иначе alembic стучится в ещё
# не поднявшийся PostgreSQL. ``UV_NO_SYNC`` снимает повторную синхронизацию
# в каждом из процессов: она уже сделана строкой выше.
start:
	docker compose up -d --wait postgres-db redis
	uv sync
	uv run alembic upgrade head
	REDIS_URL=$(REDIS_URL) UV_NO_SYNC=1 uv run honcho start

# Только инфраструктура: PostgreSQL и Redis.
services:
	docker compose up -d --wait postgres-db redis

migrate:
	uv run alembic upgrade head

bot:
	uv run bot

server:
	uv run server

worker:
	uv run taskiq worker vkt_bot.worker.app:broker --reload

scheduler:
	uv run taskiq scheduler vkt_bot.worker.app:scheduler

export_schema:
	uv run export_schema

generate_client:
	uv run export_schema
	cd control-panel-app && pnpm run openapi-ts --input ../openapi.json
	# Генератор пишет со своим форматированием, а в репозитории клиент
	# лежит прогнанным через prettier. Без этого шага каждая перегенерация
	# давала бы тысячи строк diff'а на одних кавычках и точках с запятой.
	cd control-panel-app && pnpm exec prettier --write --log-level warn src/client
