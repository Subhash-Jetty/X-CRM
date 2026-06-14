"""
Database connection and session management using SQLAlchemy async.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


# Create engine with driver-specific options (sqlite vs asyncpg)
db_url = settings.DATABASE_URL.strip()
use_sqlite = db_url.startswith("sqlite") or "aiosqlite" in db_url

if use_sqlite:
    engine = create_async_engine(
        db_url,
        echo=settings.DEBUG,
    )
else:
    engine = create_async_engine(
        db_url,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args={
            "statement_cache_size": 0,           # Disable asyncpg's internal cache
            "prepared_statement_name_func": lambda: f"__asyncpg_{__import__('uuid').uuid4().hex}__",
        },
    )

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
