"""
XENO CRM Backend — FastAPI Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
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

# Custom middleware to handle OPTIONS preflight requests blindly
@app.middleware("http")
async def handle_options_request(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        # Echo the requested headers or fallback to *
        req_headers = request.headers.get("Access-Control-Request-Headers", "*")
        response.headers["Access-Control-Allow-Headers"] = req_headers
        return response
    return await call_next(request)

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
