"""
XENO CRM Backend — FastAPI Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.routers import customers, orders, segments, campaigns, receipts, ai


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="XENO CRM API",
    description="AI-Native Mini CRM for Reaching Shoppers",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for deployed demo (no cookie auth used)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(segments.router, prefix="/api/segments", tags=["Segments"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Campaigns"])
app.include_router(receipts.router, prefix="/api/receipts", tags=["Receipts"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI Agent"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "xeno-crm"}
