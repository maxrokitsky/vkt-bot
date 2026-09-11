import datetime
import arrow


def now() -> datetime.datetime:
    return datetime.datetime().now(datetime.timezone.utc)


def localize_datetime(dt: datetime.datetime) -> str:
    return arrow.get(dt).humanize(locale="ru")


def utcnow() -> datetime.datetime:
    """Текущее время UTC без таймзоны.

    Наивный UTC — общий формат хранения в базе: колонки объявлены без
    таймзоны, и наивное значение одинаково ложится и в PostgreSQL, и в
    SQLite. ``now()`` рядом оставлен как есть — он сломан, и это
    зафиксировано тестом.
    """
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def to_naive_utc(dt: datetime.datetime) -> datetime.datetime:
    """Привести время к наивному UTC.

    В событиях VK Teams ``timestamp`` — unix-время, pydantic отдаёт его
    с таймзоной; в базе лежит наивное.
    """
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(datetime.UTC).replace(tzinfo=None)
