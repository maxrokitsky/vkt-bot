"""Инструменты агента.

Все — read-only: подтверждения им не нужны, а модель на них уже полезна.
Мутирующие (``assign_role``, ``unassign_role``, ``create_webhook``) —
вторая фаза; политика подтверждений под них уже заложена в ``vkt_agent``.

Порядок регистрации значения не имеет: реестр отдаёт инструменты
отсортированными по имени, чтобы префикс промпта не плавал и кэш у шлюза
попадал.
"""

from vkt_agent import ToolRegistry

registry = ToolRegistry()

from . import chats, events, messages, roles  # noqa: E402, F401  (регистрация)

__all__ = ("registry",)
