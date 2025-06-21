from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vkt_bot.teams_bot.config import settings

engine = create_async_engine(str(settings.db_url))
async_session = async_sessionmaker(engine, expire_on_commit=False)
