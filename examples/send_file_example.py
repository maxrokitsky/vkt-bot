"""
Пример использования метода send_file в VK Teams клиенте.

Для запуска:
    python examples/send_file_example.py --token YOUR_BOT_TOKEN --chat-id CHAT_ID

Доступные опции:
    --token TOKEN          Токен бота (обязательно)
    --chat-id CHAT_ID      ID чата (обязательно)
    --file-id FILE_ID      Отправить уже загруженный файл по file_id
    --file-path FILE_PATH  Отправить локальный файл
    --url URL              Отправить файл по URL
    --caption CAPTION      Подпись к файлу
"""

import asyncio
import argparse
from pathlib import Path

from vkteams_client import VKTeams


async def main():
    parser = argparse.ArgumentParser(
        description="Отправить файл через VK Teams Bot API"
    )
    parser.add_argument("--token", required=True, help="Токен бота")
    parser.add_argument("--chat-id", required=True, help="ID чата")
    parser.add_argument("--file-id", help="Отправить уже загруженный файл по file_id")
    parser.add_argument("--file-path", help="Отправить локальный файл")
    parser.add_argument("--url", help="Отправить файл по URL")
    parser.add_argument("--caption", help="Подпись к файлу")

    args = parser.parse_args()

    # Создаем клиент
    client = VKTeams(token=args.token)

    try:
        if args.file_id:
            # Отправка уже загруженного файла по file_id
            print(f"Отправка файла по file_id: {args.file_id}")
            result = await client.send_file(
                chat_id=args.chat_id,
                file_id=args.file_id,
                caption=args.caption,
            )
            print(f"✅ Файл отправлен! msgId: {result.msgId}")

        elif args.file_path:
            # Отправка локального файла
            file_path = Path(args.file_path)
            if not file_path.exists():
                print(f"❌ Файл не найден: {args.file_path}")
                return

            print(f"Отправка локального файла: {file_path}")
            file_content = file_path.read_bytes()

            result = await client.send_file(
                chat_id=args.chat_id,
                file=file_content,
                filename=file_path.name,
                caption=args.caption,
            )
            from vkteams_client import MsgLoadFileResponse

            if isinstance(result, MsgLoadFileResponse):
                print(
                    f"✅ Файл отправлен! fileId: {result.fileId}, msgId: {result.msgId}"
                )
            else:
                print(f"✅ Файл отправлен! msgId: {result.msgId}")

        elif args.url:
            # Отправка файла по URL
            print(f"Отправка файла по URL: {args.url}")
            result = await client.send_file_from_url(
                chat_id=args.chat_id,
                url=args.url,
                caption=args.caption,
            )
            print(f"✅ Файл отправлен! fileId: {result.fileId}, msgId: {result.msgId}")

        else:
            print(
                "❌ Не указан способ отправки файла. Используйте --file-id, --file-path или --url"
            )

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
