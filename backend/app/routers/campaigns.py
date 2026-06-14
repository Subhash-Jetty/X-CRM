"""
Campaign API routes — CRUD, send, stats.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Campaign, Communication
from app.schemas import (
    CampaignCreate, CampaignResponse, CommunicationResponse,
    MessageResponse,
)
from app.services.campaign_engine import (
    CampaignDispatchError,
    send_campaign,
    get_campaign_stats,
)

router = APIRouter()


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    """List all campaigns."""
    result = await db.execute(
        select(Campaign).order_by(desc(Campaign.created_at))
    )
    campaigns = result.scalars().all()
    return [CampaignResponse.model_validate(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single campaign."""
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}/stats")
async def campaign_stats(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get campaign delivery funnel stats."""
    try:
        stats = await get_campaign_stats(db, campaign_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{campaign_id}/communications", response_model=list[CommunicationResponse])
async def campaign_communications(
    campaign_id: UUID,
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List communications for a campaign, optionally filtered by status."""
    query = select(Communication).where(Communication.campaign_id == campaign_id)
    if status:
        query = query.where(Communication.status == status)
    query = query.order_by(desc(Communication.created_at))

    result = await db.execute(query)
    comms = result.scalars().all()
    return [CommunicationResponse.model_validate(c) for c in comms]


@router.post("", response_model=CampaignResponse)
async def create_campaign(payload: CampaignCreate, db: AsyncSession = Depends(get_db)):
    """Create a new campaign."""
    campaign = Campaign(
        name=payload.name,
        segment_id=payload.segment_id,
        message_template=payload.message_template,
        channel=payload.channel,
        scheduled_at=payload.scheduled_at,
    )
    db.add(campaign)
    await db.flush()
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/send", response_model=MessageResponse)
async def trigger_send(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    """Trigger sending a campaign to all segment members."""
    try:
        count = await send_campaign(db, campaign_id)
        return MessageResponse(
            message=f"Campaign sent to {count} recipients",
            count=count,
        )
    except CampaignDispatchError as e:
        await db.commit()
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
