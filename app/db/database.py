# app/db/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Parse DATABASE_URL — strip pgbouncer param since asyncpg doesn't understand it,
# but we need to tell asyncpg to use "statement_cache_size=0" for PgBouncer compatibility.
_raw_url = settings.DATABASE_URL

# Remove ?pgbouncer=true or &pgbouncer=true from URL if present
if "?pgbouncer=true" in _raw_url:
    _raw_url = _raw_url.replace("?pgbouncer=true", "")
elif "&pgbouncer=true" in _raw_url:
    _raw_url = _raw_url.replace("&pgbouncer=true", "")

engine = create_async_engine(
    _raw_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    # PgBouncer in transaction mode does not support prepared statements,
    # so we must disable the statement cache.
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0}
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
