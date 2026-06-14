import asyncio
import json
import os
import sys

# Add backend dir to path so we can import backend app
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_dir)

# Change working directory to backend so pydantic-settings finds .env
os.chdir(backend_dir)

from app.database import engine, async_session_maker
from app.services.ingestion import ingest_customers, ingest_orders
from app.models import Base

async def ingest_data():
    # Keep the local SQLite demo path self-contained. Production deployments still
    # use schema.sql/migrations, but create_all is harmless for existing tables.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    seed_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    print("Loading JSON files...")
    with open(os.path.join(seed_dir, "customers.json")) as f:
        customers_data = json.load(f)["customers"]
        
    with open(os.path.join(seed_dir, "orders.json")) as f:
        orders_data = json.load(f)["orders"]

    print(f"Loaded {len(customers_data)} customers and {len(orders_data)} orders.")
    
    async with async_session_maker() as session:
        try:
            print("Ingesting customers...")
            await ingest_customers(session, customers_data)
            
            print("Ingesting orders and updating customer aggregates (this might take a few seconds)...")
            # To avoid blowing up memory with 5000 records at once, let's chunk them
            chunk_size = 1000
            for i in range(0, len(orders_data), chunk_size):
                chunk = orders_data[i:i + chunk_size]
                await ingest_orders(session, chunk)
                print(f"Processed {min(i + chunk_size, len(orders_data))}/{len(orders_data)} orders...")
            
            await session.commit()
            print("[OK] Ingestion complete! All data committed successfully.")
        except Exception as e:
            await session.rollback()
            print(f"[ERROR] Ingestion failed: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(ingest_data())
