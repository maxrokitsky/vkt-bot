# Локальный запуск: honcho поднимает все четыре процесса разом (make start).
# Инфраструктуру — PostgreSQL и Redis — поднимает docker compose, её тут нет.
#
# Без REDIS_URL воркер и планировщик работать не могут: у брокера в памяти
# нечего слушать. `make start` подставляет адрес проброшенного порта, если в
# `.env` своего нет.
bot: uv run bot
server: uv run server
worker: uv run taskiq worker vkt_bot.worker.app:broker --workers 1 --max-async-tasks 3 --reload
scheduler: uv run taskiq scheduler vkt_bot.worker.app:scheduler
