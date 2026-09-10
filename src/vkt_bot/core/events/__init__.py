"""Доменные события: реестр типов и точка испускания."""

from .emit import Actor, emit
from .registry import EventSpec, EventType, all_specs, get, register

__all__ = (
    "Actor",
    "EventSpec",
    "EventType",
    "all_specs",
    "emit",
    "get",
    "register",
)
