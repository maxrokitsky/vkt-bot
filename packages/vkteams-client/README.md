# vkteams-client

Асинхронный клиент для VK Teams Bot API

```python
import asyncio
from vkteams_client import VkTeams, Event, EventType

bot = VkTeams('токен')


async def start_polling():
    last_event_id: int = 0

    while True:
        response = await self.bot.get_events(
            last_event_id=last_event_id, poll_time=20
        )
        for event in response.events:
            await handle_event(event)
            last_event_id = max(last_event_id, event.eventId)


async def handle_event(event: Event) -> None:
    if event.type == EventType.NEW_MESSAGE:
        await bot.send_text(event.payload.chat.chatId, "Hello, world!")


async def main():
    print(await bot.get_self())
    await bot.send_text('admin@example.com', 'Bot started!')
    await start_polling()
    await bot.close()


if __name__ == '__main__':
    asyncio.run(main())
```