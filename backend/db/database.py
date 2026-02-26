from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    from db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        result = await conn.execute(text("PRAGMA table_info(sessions)"))
        session_columns = {row[1] for row in result.fetchall()}
        if "blueprint_markdown" not in session_columns:
            await conn.execute(text("ALTER TABLE sessions ADD COLUMN blueprint_markdown TEXT"))


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
