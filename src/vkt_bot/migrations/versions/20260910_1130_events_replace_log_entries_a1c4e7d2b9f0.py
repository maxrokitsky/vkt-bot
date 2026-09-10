"""events replace log entries.

Revision ID: a1c4e7d2b9f0
Revises: 4d520a5b73f9
Create Date: 2026-09-10 11:30:00.000000

Журнал действий превращается в журнал событий: пара «действие + сущность»
складывается в один тип (``role.assigned``), появляются источник,
значимость, чат и ``trace_id`` для связи с логами.

Таблица переименовывается, данные переносятся: история действий за всё
время не должна пропасть из панели.

Перечисления переезжают из нативных типов PostgreSQL в VARCHAR — иначе
каждое новое значение требовало бы ``ALTER TYPE``, а плагины не смогли бы
заводить свои типы сущностей вовсе.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c4e7d2b9f0"
down_revision: Union[str, None] = "4d520a5b73f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_INDEXES = (
    "ix_log_entries_action_type",
    "ix_log_entries_actor_id",
    "ix_log_entries_actor_type",
    "ix_log_entries_bot_user_id",
    "ix_log_entries_entity_type",
    "ix_log_entries_timestamp",
    "ix_log_entries_web_user_username",
)

#: Старое действие → хвост нового типа.
ACTION_SUFFIX = {
    "create": "created",
    "update": "updated",
    "delete": "deleted",
    "assign": "assigned",
    "unassign": "unassigned",
}


def upgrade() -> None:
    """Upgrades db schema."""
    for index in OLD_INDEXES:
        op.drop_index(index, table_name="log_entries", if_exists=True)

    op.rename_table("log_entries", "events")

    op.alter_column("events", "timestamp", new_column_name="ts")
    op.alter_column("events", "description", new_column_name="summary")
    op.alter_column("events", "details", new_column_name="payload")

    # Нативные ENUM'ы PostgreSQL → строки.
    for column, length in (
        ("actor_type", 32),
        ("action_type", 32),
        ("entity_type", 64),
    ):
        op.alter_column(
            "events",
            column,
            type_=sa.String(length=length),
            existing_nullable=False,
            postgresql_using=f"{column}::text",
        )

    op.add_column("events", sa.Column("type", sa.String(length=64), nullable=True))
    op.add_column("events", sa.Column("source", sa.String(length=32), nullable=True))
    op.add_column("events", sa.Column("severity", sa.String(length=32), nullable=True))
    op.add_column("events", sa.Column("chat_id", sa.String(), nullable=True))
    op.add_column("events", sa.Column("trace_id", sa.String(length=64), nullable=True))

    # --- перенос данных ---
    # Нативный ENUM хранил имена членов (``CREATE``, ``ROLE``), а не их
    # значения, — отсюда lower() во всех сравнениях ниже.
    cases = " ".join(
        f"WHEN lower(action_type) = '{action}' THEN '{suffix}'"
        for action, suffix in ACTION_SUFFIX.items()
    )
    op.execute(  # noqa: S608 — подставляются только константы из ACTION_SUFFIX
        f"""
        UPDATE events
        SET
            entity_type = lower(entity_type),
            type = lower(entity_type) || '.'
                || (CASE {cases} ELSE lower(action_type) END)
        """
    )
    # Назначение роли жило под сущностью role_assignment — в новой схеме
    # это действие над ролью.
    op.execute(
        """
        UPDATE events
        SET type = 'role.' || split_part(type, '.', 2)
        WHERE type LIKE 'role_assignment.%'
        """
    )
    op.execute(
        """
        UPDATE events
        SET
            source = CASE lower(actor_type)
                WHEN 'web_user' THEN 'panel'
                WHEN 'bot_user' THEN 'command'
                ELSE 'system'
            END,
            severity = 'info',
            actor_type = CASE lower(actor_type)
                WHEN 'web_user' THEN 'user'
                WHEN 'bot_user' THEN 'user'
                ELSE 'system'
            END,
            summary = COALESCE(summary, type)
        """
    )

    op.alter_column("events", "type", nullable=False)
    op.alter_column("events", "source", nullable=False)
    op.alter_column("events", "severity", nullable=False)
    op.alter_column("events", "summary", nullable=False)
    op.alter_column("events", "entity_type", nullable=True)
    op.alter_column("events", "entity_id", nullable=True)

    op.drop_column("events", "action_type")
    op.drop_column("events", "web_user_username")
    op.drop_column("events", "bot_user_id")

    op.create_index(op.f("ix_events_ts"), "events", ["ts"], unique=False)
    op.create_index(op.f("ix_events_type"), "events", ["type"], unique=False)
    op.create_index(op.f("ix_events_source"), "events", ["source"], unique=False)
    op.create_index(op.f("ix_events_actor_id"), "events", ["actor_id"], unique=False)
    op.create_index(op.f("ix_events_chat_id"), "events", ["chat_id"], unique=False)
    op.create_index(op.f("ix_events_trace_id"), "events", ["trace_id"], unique=False)
    op.create_index("ix_events_chat_id_ts", "events", ["chat_id", "ts"], unique=False)
    op.create_index("ix_events_type_ts", "events", ["type", "ts"], unique=False)
    op.create_index("ix_events_actor_id_ts", "events", ["actor_id", "ts"], unique=False)

    # Нативные типы больше никем не используются.
    for enum_name in ("actiontype", "actortype", "entitytype"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")


def downgrade() -> None:
    """Downgrades db schema."""
    action_type = sa.Enum(
        "CREATE", "UPDATE", "DELETE", "ASSIGN", "UNASSIGN", name="actiontype"
    )
    actor_type = sa.Enum("WEB_USER", "BOT_USER", "SYSTEM", name="actortype")
    entity_type = sa.Enum(
        "USER",
        "CHAT_USER",
        "ROLE",
        "CHAT",
        "ROLE_ASSIGNMENT",
        "CHAT_MEMBERSHIP",
        "BOT_SETTINGS",
        name="entitytype",
    )

    for index in (
        "ix_events_ts",
        "ix_events_type",
        "ix_events_source",
        "ix_events_actor_id",
        "ix_events_chat_id",
        "ix_events_trace_id",
        "ix_events_chat_id_ts",
        "ix_events_type_ts",
        "ix_events_actor_id_ts",
    ):
        op.drop_index(index, table_name="events", if_exists=True)

    op.add_column("events", sa.Column("action_type", sa.String(length=32)))
    op.add_column("events", sa.Column("web_user_username", sa.String()))
    op.add_column("events", sa.Column("bot_user_id", sa.String()))

    cases = " ".join(
        f"WHEN type LIKE '%.{suffix}' THEN '{action}'"
        for action, suffix in ACTION_SUFFIX.items()
    )
    op.execute(  # noqa: S608 — подставляются только константы из ACTION_SUFFIX
        f"""
        UPDATE events
        SET
            action_type = CASE {cases} ELSE 'update' END,
            entity_type = COALESCE(entity_type, split_part(type, '.', 1)),
            entity_id = COALESCE(entity_id, ''),
            actor_type = CASE actor_type WHEN 'user' THEN 'web_user' ELSE 'system' END,
            bot_user_id = actor_id
        """
    )

    op.drop_column("events", "trace_id")
    op.drop_column("events", "chat_id")
    op.drop_column("events", "severity")
    op.drop_column("events", "source")
    op.drop_column("events", "type")

    op.alter_column("events", "entity_type", nullable=False)
    op.alter_column("events", "entity_id", nullable=False)
    op.alter_column("events", "summary", nullable=True)
    op.alter_column("events", "ts", new_column_name="timestamp")
    op.alter_column("events", "summary", new_column_name="description")
    op.alter_column("events", "payload", new_column_name="details")

    op.rename_table("events", "log_entries")

    action_type.create(op.get_bind(), checkfirst=True)
    actor_type.create(op.get_bind(), checkfirst=True)
    entity_type.create(op.get_bind(), checkfirst=True)
    for column, enum in (
        ("actor_type", actor_type),
        ("action_type", action_type),
        ("entity_type", entity_type),
    ):
        op.alter_column(
            "log_entries",
            column,
            type_=enum,
            postgresql_using=f"upper({column})::{enum.name}",
        )

    op.create_index(
        op.f("ix_log_entries_timestamp"), "log_entries", ["timestamp"], unique=False
    )
    op.create_index(
        op.f("ix_log_entries_actor_type"), "log_entries", ["actor_type"], unique=False
    )
    op.create_index(
        op.f("ix_log_entries_actor_id"), "log_entries", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_log_entries_action_type"), "log_entries", ["action_type"], unique=False
    )
    op.create_index(
        op.f("ix_log_entries_entity_type"), "log_entries", ["entity_type"], unique=False
    )
    op.create_index(
        op.f("ix_log_entries_bot_user_id"), "log_entries", ["bot_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_log_entries_web_user_username"),
        "log_entries",
        ["web_user_username"],
        unique=False,
    )
