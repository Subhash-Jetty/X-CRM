"""
Customer API routes — list, detail, bulk ingest.
"""
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Customer, Order
from app.schemas import (
    CustomerResponse, CustomerBulkIngest, MessageResponse,
    PaginatedResponse, OrderResponse,
)
from app.services.ingestion import ingest_customers

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("", response_model=PaginatedResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    """List all customers with pagination, search, and sorting."""
    query = select(Customer)

    # Search filter
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Customer.name.ilike(search_filter)) |
            (Customer.email.ilike(search_filter)) |
            (Customer.phone.ilike(search_filter))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Sorting
    sort_col = getattr(Customer, sort_by, Customer.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(sort_col)

    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    customers = result.scalars().all()

    items_list: list[CustomerResponse] = []
    for c in customers:
        try:
            data = {
                "id": c.id,
                "name": c.name if c.name is not None else "Unknown",
                "email": c.email,
                "phone": c.phone,
                "total_spend": float(c.total_spend) if c.total_spend is not None else 0.0,
                "order_count": int(c.order_count) if c.order_count is not None else 0,
                "last_order_date": c.last_order_date,
                "first_order_date": c.first_order_date,
                "avg_order_value": float(c.avg_order_value) if c.avg_order_value is not None else 0.0,
                "tags": c.tags or [],
                "created_at": c.created_at,
            }
            items_list.append(CustomerResponse.model_validate(data))
        except Exception as e:
            logger.warning("Failed to validate customer %s: %s", getattr(c, "id", None), e)
            # Best-effort fallback: include minimal fields so UI can show the row
            items_list.append(CustomerResponse.model_validate({
                "id": c.id,
                "name": c.name or "Unknown",
                "email": c.email,
                "phone": c.phone,
                "tags": c.tags or [],
                "created_at": c.created_at,
            }))

    return PaginatedResponse(
        items=items_list,
        total=total or 0,
        page=page,
        page_size=page_size,
        total_pages=(int(total or 0) + page_size - 1) // page_size,
    )


@router.get("/stats")
async def customer_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregate customer statistics for the dashboard."""
    result = await db.execute(
        select(
            func.count(Customer.id).label("total_customers"),
            func.coalesce(func.avg(Customer.total_spend), 0).label("avg_total_spend"),
            func.coalesce(func.avg(Customer.avg_order_value), 0).label("avg_order_value"),
            func.coalesce(func.sum(Customer.total_spend), 0).label("total_revenue"),
            func.coalesce(func.avg(Customer.order_count), 0).label("avg_orders_per_customer"),
        )
    )
    row = result.one()
    return {
        "total_customers": row.total_customers,
        "avg_total_spend": round(float(row.avg_total_spend), 2),
        "avg_order_value": round(float(row.avg_order_value), 2),
        "total_revenue": round(float(row.total_revenue), 2),
        "avg_orders_per_customer": round(float(row.avg_orders_per_customer), 1),
    }


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single customer by ID."""
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}/orders", response_model=list[OrderResponse])
async def get_customer_orders(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all orders for a customer."""
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(desc(Order.created_at))
    )
    orders = result.scalars().all()
    return [OrderResponse.model_validate(o) for o in orders]


@router.post("/ingest", response_model=MessageResponse)
async def bulk_ingest(payload: CustomerBulkIngest, db: AsyncSession = Depends(get_db)):
    """Bulk ingest customers. Upserts by email."""
    data = [c.model_dump() for c in payload.customers]
    count = await ingest_customers(db, data)
    return MessageResponse(message=f"Successfully ingested {count} customers", count=count)
