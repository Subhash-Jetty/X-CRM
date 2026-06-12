"""
Receipt webhook handler — processes delivery callbacks from the channel service.
"""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Communication, Campaign
from app.schemas import DeliveryReceipt, DeliveryReceiptBatch

router = APIRouter()

# Status progression ordering (for idempotency — never go backwards)
STATUS_ORDER = {
    "queued": 0,
    "sent": 1,
    "delivered": 2,
    "failed": 2,
    "opened": 3,
    "read": 4,
    "clicked": 5,
    "converted": 6,
}


@router.post("")
async def receive_receipt(receipt: DeliveryReceipt, db: AsyncSession = Depends(get_db)):
    """Process a single delivery receipt from the channel service."""
    await process_receipt(db, receipt)
    return {"status": "ok"}


@router.post("/batch")
async def receive_batch(batch: DeliveryReceiptBatch, db: AsyncSession = Depends(get_db)):
    """Process a batch of delivery receipts."""
    processed = 0
    for receipt in batch.receipts:
        try:
            await process_receipt(db, receipt)
            processed += 1
        except Exception:
            continue  # Log and skip failed receipts
    return {"status": "ok", "processed": processed}


async def process_receipt(db: AsyncSession, receipt: DeliveryReceipt):
    """
    Process a single delivery receipt:
    1. Update communication status
    2. Update campaign aggregate counters
    """
    # Get the communication
    result = await db.execute(
        select(Communication).where(Communication.id == receipt.communication_id)
    )
    comm = result.scalar_one_or_none()
    if not comm:
        return  # Silently skip unknown communications

    # Idempotency: don't go backwards in status
    current_order = STATUS_ORDER.get(comm.status, 0)
    new_order = STATUS_ORDER.get(receipt.status, 0)
    if new_order <= current_order and receipt.status != "failed":
        return  # Skip — already at a later status

    old_status = comm.status
    comm.status = receipt.status

    # Set timestamps
    timestamp = receipt.timestamp or datetime.utcnow()
    if receipt.status == "sent":
        comm.sent_at = timestamp
    elif receipt.status == "delivered":
        comm.delivered_at = timestamp
    elif receipt.status == "failed":
        comm.failed_at = timestamp
        comm.error_message = receipt.error_message
    elif receipt.status == "opened":
        comm.opened_at = timestamp
    elif receipt.status == "read":
        comm.read_at = timestamp
    elif receipt.status == "clicked":
        comm.clicked_at = timestamp
    elif receipt.status == "converted":
        comm.converted_at = timestamp

    # Update campaign counters
    campaign_id = comm.campaign_id
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign:
        # Increment new status counter
        counter_map = {
            "sent": "sent_count",
            "delivered": "delivered_count",
            "failed": "failed_count",
            "opened": "opened_count",
            "read": "read_count",
            "clicked": "clicked_count",
            "converted": "converted_count",
        }
        counter = counter_map.get(receipt.status)
        if counter:
            current = getattr(campaign, counter, 0) or 0
            setattr(campaign, counter, current + 1)

        # Check if campaign is complete (all communications have a terminal status)
        total = campaign.total_recipients or 0
        terminal_count = (campaign.delivered_count or 0) + (campaign.failed_count or 0)
        if terminal_count >= total and total > 0:
            campaign.status = "completed"
            campaign.completed_at = datetime.utcnow()

    await db.flush()
