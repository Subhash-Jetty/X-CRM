"""
Segment API routes — CRUD, preview, refresh.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Segment, SegmentMember, Customer, Campaign
from app.schemas import (
    SegmentCreate, SegmentResponse, CustomerResponse,
    PaginatedResponse, MessageResponse,
)
from app.services.segmentation import (
    create_segment_with_members,
    refresh_segment_members,
    preview_segment,
)

router = APIRouter()


@router.get("", response_model=list[SegmentResponse])
async def list_segments(db: AsyncSession = Depends(get_db)):
    """List all segments."""
    result = await db.execute(
        select(Segment).order_by(desc(Segment.created_at))
    )
    segments = result.scalars().all()
    return [SegmentResponse.model_validate(s) for s in segments]


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(segment_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single segment."""
    result = await db.execute(
        select(Segment).where(Segment.id == segment_id)
    )
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return SegmentResponse.model_validate(segment)


@router.get("/{segment_id}/members", response_model=PaginatedResponse)
async def get_segment_members(
    segment_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get customers in a segment."""
    # Count total members
    count_result = await db.execute(
        select(func.count(SegmentMember.customer_id))
        .where(SegmentMember.segment_id == segment_id)
    )
    total = count_result.scalar()

    # Get paginated members
    result = await db.execute(
        select(Customer)
        .join(SegmentMember, SegmentMember.customer_id == Customer.id)
        .where(SegmentMember.segment_id == segment_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    customers = result.scalars().all()

    return PaginatedResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("", response_model=SegmentResponse)
async def create_segment(payload: SegmentCreate, db: AsyncSession = Depends(get_db)):
    """Create a new segment from structured rules."""
    rules_dicts = [r.model_dump() for r in payload.rules]
    segment = await create_segment_with_members(
        db=db,
        name=payload.name,
        description=payload.description,
        rules=rules_dicts,
        natural_language_query=payload.natural_language_query,
        is_ai_generated=payload.is_ai_generated,
    )
    return SegmentResponse.model_validate(segment)


@router.post("/{segment_id}/refresh", response_model=MessageResponse)
async def refresh_segment(segment_id: UUID, db: AsyncSession = Depends(get_db)):
    """Re-evaluate segment rules and refresh membership."""
    count = await refresh_segment_members(db, segment_id)
    return MessageResponse(message=f"Segment refreshed with {count} members", count=count)


@router.post("/preview")
async def preview_segment_rules(
    payload: SegmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Preview matching customers without creating a segment."""
    rules_dicts = [r.model_dump() for r in payload.rules]
    customers, total = await preview_segment(db, rules_dicts, limit=10)
    return {
        "total_matching": total,
        "preview": [CustomerResponse.model_validate(c) for c in customers],
    }


@router.delete("/{segment_id}", response_model=MessageResponse)
async def delete_segment(segment_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a segment and its members."""
    result = await db.execute(
        select(Segment).where(Segment.id == segment_id)
    )
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Remove references from campaigns before deleting to avoid IntegrityError
    await db.execute(
        update(Campaign).where(Campaign.segment_id == segment_id).values(segment_id=None)
    )

    await db.delete(segment)
    return MessageResponse(message="Segment deleted")
