"""
Database connection and session management using SQLAlchemy async.
"""
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


def is_sqlite_url(db_url: str) -> bool:
    """Return whether the configured database URL targets SQLite."""
    return db_url.startswith("sqlite") or "aiosqlite" in db_url


def build_engine_kwargs(db_url: str, debug: bool) -> dict[str, Any]:
    """Build driver-specific SQLAlchemy engine options."""
    if is_sqlite_url(db_url):
        return {"echo": debug}

    return {
        "echo": debug,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "connect_args": {
            # Supabase's transaction pooler uses PgBouncer, so disable both
            # asyncpg's cache and SQLAlchemy's asyncpg prepared statement cache.
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    }


db_url = settings.DATABASE_URL.strip()
engine = create_async_engine(db_url, **build_engine_kwargs(db_url, settings.DEBUG))

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
async_session_maker = async_session  # Alias used by seed scripts


async def get_db() -> AsyncSession:
    """Dependency: yield a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database — create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Cleanup database connections."""
    await engine.dispose()
