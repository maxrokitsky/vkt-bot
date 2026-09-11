"""messages history.

Revision ID: c3f1a2b4d5e6
Revises: a1c4e7d2b9f0
Create Date: 2026-09-10 15:00:00.000000

История сообщений чатов. До этой таблицы сообщения не хранились нигде, а
прочитать их у Bot API нельзя — метода вроде ``messages/get`` в спеке нет.
Поэтому история набирается только вперёд, с момента накатывания миграции.

Внешних ключей нет намеренно: у обсуждения свой ``chatId``, которого в
``chats`` не существует, а автор реплики может быть ещё не заведён в
``chat_users`` — строки там создаёт поток событий о составе чата, а не
поток сообщений.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3f1a2b4d5e6"
down_revision: Union[str, None] = "a1c4e7d2b9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrades db schema."""
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("msg_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "is_outgoing", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id", "msg_id", name="uq_messages_chat_msg"),
    )
    op.create_index("ix_messages_chat_id", "messages", ["chat_id"])
    op.create_index("ix_messages_user_id", "messages", ["user_id"])
    op.create_index("ix_messages_ts", "messages", ["ts"])
    # Единственный горячий запрос: последние N сообщений чата.
    op.create_index("ix_messages_chat_id_ts", "messages", ["chat_id", "ts"])


def downgrade() -> None:
    """Downgrades db schema."""
    op.drop_index("ix_messages_chat_id_ts", table_name="messages")
    op.drop_index("ix_messages_ts", table_name="messages")
    op.drop_index("ix_messages_user_id", table_name="messages")
    op.drop_index("ix_messages_chat_id", table_name="messages")
    op.drop_table("messages")
