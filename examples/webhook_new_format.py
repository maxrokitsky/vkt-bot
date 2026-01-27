#!/usr/bin/env python3
"""
Пример использования нового формата вебхуков.

Новый формат поддерживает отправку файлов через:
1. Base64 encoded content
2. Data URL

Примеры запросов:
"""

import base64
import json

# Пример 1: Отправка текста
text_example = {
    "text": "Привет, мир! Это тестовое сообщение.",
    "parse_mode": "MarkdownV2",
}

# Пример 2: Отправка файла через base64
# Создаем тестовый файл
file_content = "Это содержимое тестового файла.\nВторая строка файла.".encode("utf-8")
file_base64 = base64.b64encode(file_content).decode("utf-8")

file_base64_example = {
    "file": {
        "content": file_base64,
        "filename": "test_file.txt",
        "caption": "Вот ваш файл с текстом",
    },
    "parse_mode": "MarkdownV2",
}

# Пример 3: Отправка файла через data URL
data_url_example = {
    "file": {
        "data_url": f"data:text/plain;base64,{file_base64}",
        "filename": "test_file.txt",
        "caption": "Файл отправлен через data URL",
    },
}

# Пример 4: Отправка изображения через base64
# Создаем простой PNG изображение (1x1 пиксель, черный)
png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

image_example = {
    "file": {
        "content": png_base64,
        "filename": "image.png",
        "caption": "Тестовое изображение",
    },
}

print("Примеры запросов для нового формата вебхуков:")
print("=" * 60)

print("\n1. Отправка текста:")
print(json.dumps(text_example, indent=2, ensure_ascii=False))

print("\n2. Отправка файла через base64:")
print(json.dumps(file_base64_example, indent=2, ensure_ascii=False))

print("\n3. Отправка файла через data URL:")
print(json.dumps(data_url_example, indent=2, ensure_ascii=False))

print("\n4. Отправка изображения через base64:")
print(json.dumps(image_example, indent=2, ensure_ascii=False))

print("\n" + "=" * 60)
print("Пример cURL запроса:")
print("""
# Отправка текста
curl -X POST \\
  http://localhost:8000/webhooks/{webhook_id} \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "Привет, мир!",
    "parse_mode": "MarkdownV2"
  }'

# Отправка файла через base64
curl -X POST \\
  http://localhost:8000/webhooks/{webhook_id} \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "file": {
      "content": "SGVsbG8sIFdvcmxkIQ==",
      "filename": "hello.txt",
      "caption": "Вот ваш файл"
    }
  }'
""")
