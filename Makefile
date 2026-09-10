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
