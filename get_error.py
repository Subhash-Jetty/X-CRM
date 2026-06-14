import asyncio
import sys
import os

sys.path.append('backend')
from app.models import Communication
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    'postgresql+asyncpg://postgres.euntouwflhlzgegmmxgj:YxcL7pYFbGqbceA4@aws-1-ap-south-1.pooler.supabase.com:6543/postgres',
    connect_args={
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
    }
)

async def main():
    async with AsyncSession(engine) as db:
        result = await db.execute(
            select(Communication)
            .where(Communication.status == 'failed')
            .order_by(Communication.created_at.desc())
            .limit(1)
        )
        comm = result.scalar_one_or_none()
        if comm:
            print(f"LATEST FAILED COMM ERROR: {comm.error_message}")
            print(f"CHANNEL: {comm.channel}")
            print(f"FAILED AT: {comm.failed_at}")
        else:
            print("No failed communications found.")

asyncio.run(main())
