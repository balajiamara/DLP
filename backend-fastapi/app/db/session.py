from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings

settings = get_settings()

# Connection pool settings for Supabase (free tier compatibility):
# 1. pool_size & max_overflow: kept small to avoid exhausting Supabase connection limits alongside Django.
# 2. connect_args={"statement_cache_size": 0}: Disables asyncpg's prepared statement cache.
#    This ensures complete compatibility if connecting via Supabase PgBouncer transaction pooler (port 6543)
#    and has no negative impact on direct connections (port 5432).
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    connect_args={"statement_cache_size": 0},
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
