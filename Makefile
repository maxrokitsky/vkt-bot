migrate:
	uv run alembic upgrade head

bot:
	uv run bot

server:
	uv run server

export_schema:
	uv run export_schema

generate_client:
	uv run export_schema
	cd control-panel-app && pnpm run openapi-ts --input ../openapi.json
	# Генератор пишет со своим форматированием, а в репозитории клиент
	# лежит прогнанным через prettier. Без этого шага каждая перегенерация
	# давала бы тысячи строк diff'а на одних кавычках и точках с запятой.
	cd control-panel-app && pnpm exec prettier --write --log-level warn src/client
