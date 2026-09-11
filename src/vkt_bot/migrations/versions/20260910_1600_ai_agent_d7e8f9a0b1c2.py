"""ai agent.

Revision ID: d7e8f9a0b1c2
Revises: c3f1a2b4d5e6
Create Date: 2026-09-10 16:00:00.000000

Таблицы плагина ``vkt-ai``: диалог с агентом, его сообщения и вызовы
инструментов.

``chat_id`` без внешнего ключа — у обсуждения свой ``chatId``, которого в
``chats`` нет. Перечисления хранятся как VARCHAR со значениями: нативный
ENUM пришлось бы менять миграцией при каждом новом состоянии.

Сообщения диалога лежат дважды: ``content`` — текст для панели, ``raw`` —
то же сообщение в формате pydantic-ai. Одного текста для продолжения
разговора не хватает: в нём нет ни вызовов инструментов, ни их
результатов.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c3f1a2b4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SESSION_STATUS = sa.Enum(
    "active",
    "waiting_approval",
    "done",
    "failed",
    "canceled",
    name="sessionstatus",
    native_enum=False,
    length=32,
)

TOOL_CALL_STATUS = sa.Enum(
    "pending",
    "approved",
    "denied",
    "executed",
    "failed",
    name="toolcallstatus",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    """Upgrades db schema."""
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=True),
        sa.Column("anchor_msg_id", sa.String(), nullable=True),
        sa.Column("status", SESSION_STATUS, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("tokens_in", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_out", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["chat_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_sessions_chat_id", "agent_sessions", ["chat_id"])
    op.create_index("ix_agent_sessions_thread_id", "agent_sessions", ["thread_id"])
    op.create_index("ix_agent_sessions_created_at", "agent_sessions", ["created_at"])

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(length=64), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["agent_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_messages_session_id", "agent_messages", ["session_id"])
    op.create_index(
        "ix_agent_messages_session_created",
        "agent_messages",
        ["session_id", "created_at"],
    )

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("args", sa.JSON(), nullable=True),
        sa.Column("status", TOOL_CALL_STATUS, nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["agent_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_tool_calls_session_id", "agent_tool_calls", ["session_id"]
    )


def downgrade() -> None:
    """Downgrades db schema."""
    op.drop_index("ix_agent_tool_calls_session_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")
    op.drop_index("ix_agent_messages_session_created", table_name="agent_messages")
    op.drop_index("ix_agent_messages_session_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_sessions_created_at", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_thread_id", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_chat_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
