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
         # Отправка файла по file_id
         await bot.send_file(
             chat_id=event.payload.chat.chatId,
             file_id="0dC76vcKS3XZOtG5DVs9y15d1daefa1ae",
             caption="Вот файл!",
         )


async def main():
    print(await bot.get_self())
    await bot.send_text('admin@example.com', 'Bot started!')
    await start_polling()
    await bot.close()


 if __name__ == '__main__':
     asyncio.run(main())

## Отправка файлов

Клиент поддерживает отправку файлов тремя способами:

### 1. Отправка уже загруженного файла по file_id

```python
result = await bot.send_file(
    chat_id="123456789@chat.agent",
    file_id="0dC76vcKS3XZOtG5DVs9y15d1daefa1ae",
    caption="Вот ваш файл!",
)
print(f"Сообщение отправлено: {result.msgId}")
```

### 2. Отправка локального файла

```python
with open("document.pdf", "rb") as f:
    file_content = f.read()

result = await bot.send_file(
    chat_id="123456789@chat.agent",
    file=file_content,
    filename="document.pdf",
    caption="Документ для вас",
)
print(f"Файл отправлен: {result.fileId}, сообщение: {result.msgId}")
```

### 3. Отправка файла по URL

```python
result = await bot.send_file_from_url(
    chat_id="123456789@chat.agent",
    url="https://example.com/document.pdf",
    caption="Файл из интернета",
)
print(f"Файл отправлен: {result.fileId}, сообщение: {result.msgId}")
```

### Дополнительные параметры

Метод `send_file` поддерживает все параметры VK Teams Bot API:
- `caption` - подпись к файлу
- `reply_msg_id` - ответ на сообщение
- `forward_chat_id`, `forward_msg_id` - пересылка сообщения
- `inline_keyboard_markup` - inline клавиатура
- `format` - форматирование текста
- `parse_mode` - режим парсинга (MarkdownV2 или HTML)
```