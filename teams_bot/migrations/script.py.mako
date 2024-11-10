"""${message}.

Revision ID: ${up_revision}
Revises:${" " if down_revision else ""}${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrades db schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrades db schema."""
    ${downgrades if downgrades else "pass"}
