build:
	docker build . -t git.rokitsky.ru/vkt-bot/vkt-bot

push:
	docker push git.rokitsky.ru/vkt-bot/vkt-bot

migrate:
	alembic upgrade head
