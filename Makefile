migrate:
	alembic upgrade head

bot:
	uv run bot

server:
	uv run server

createsuperuser:
	@echo "Creating superuser..."
	@read -p "Username: " username; \
	read -sp "Password: " password; echo; \
	read -p "Email: " email; \
	uv run python -m vkt_bot.scripts.create_admin "$$username" "$$password" "$$email"