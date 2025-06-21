import datetime
import arrow


def now() -> datetime.datetime:
    return datetime.datetime().now(datetime.timezone.utc)


def localize_datetime(dt: datetime.datetime) -> str:
    return arrow.get(dt).humanize(locale="ru")
