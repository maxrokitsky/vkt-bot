from typing import Any

import sqlalchemy as sa

from .base import Model

__all__ = ('Model', 'Statement')

type Statement = sa.Select[Any]
