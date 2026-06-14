"""
Receipt webhook handler for delivery callbacks from the channel service.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Campaign, Communication
from app.schemas import DeliveryReceipt, DeliveryReceiptBatch

router = APIRouter()

BATCH_COMMIT_SIZE = 250

STATUS_ORDER = {
    "queued": 0,
    "sent": 1,
    "failed": 1,
    "delivered": 2,
    "opened": 3,
    "read": 4,
    "clicked": 5,
    "converted": 6,
}

STATUS_COUNTERS = {
    "failed": ("failed_count",),
    "delivered": ("delivered_count",),
    "opened": ("delivered_count", "opened_count"),
    "read": ("delivered_count", "opened_count", "read_count"),
    "clicked": ("delivered_count", "opened_count", "read_count", "clicked_count"),
    "converted": (
        "delivered_count",
        "opened_count",
        "read_count",
        "clicked_count",
        "converted_count",
    ),
}


@router.post("")
async def receive_receipt(receipt: DeliveryReceipt, db: AsyncSession = Depends(get_db)):
    """Process a single delivery receipt from the channel service."""
    try:
        changed = await process_receipt(db, receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok", "processed": 1 if changed else 0}


@router.post("/batch")
async def receive_batch(batch: DeliveryReceiptBatch, db: AsyncSession = Depends(get_db)):
    """Process a batch of delivery receipts."""
    processed = 0
    skipped = 0
    rejected = 0
    receipt_ids = [receipt.communication_id for receipt in batch.receipts]

    if not receipt_ids:
        return {"status": "ok", "processed": 0, "skipped": 0, "rejected": 0}

    comms_result = await db.execute(
        select(Communication).where(Communication.id.in_(receipt_ids))
    )
    communications = {comm.id: comm for comm in comms_result.scalars().all()}

    campaign_ids = {comm.campaign_id for comm in communications.values()}
    campaigns = {}
    if campaign_ids:
        campaigns_result = await db.execute(
            select(Campaign).where(Campaign.id.in_(campaign_ids))
        )
        campaigns = {campaign.id: campaign for campaign in campaigns_result.scalars().all()}

    for receipt in batch.receipts:
        try:
            comm = communications.get(receipt.communication_id)
            if not comm:
                skipped += 1
                continue

            changed = apply_receipt_transition(
                comm=comm,
                campaign=campaigns.get(comm.campaign_id),
                receipt=receipt,
            )
            if changed:
                processed += 1
                if processed % BATCH_COMMIT_SIZE == 0:
                    await db.flush()
                    await db.commit()
            else:
                skipped += 1
        except ValueError:
            rejected += 1
    await db.flush()
    return {"status": "ok", "processed": processed, "skipped": skipped, "rejected": rejected}


def _should_accept_transition(current_status: str, new_status: str) -> bool:
    if new_status not in STATUS_ORDER:
        raise ValueError(f"Invalid receipt status: {new_status}")

    if current_status not in STATUS_ORDER:
        current_status = "queued"

    if current_status == "failed":
        return False

    if new_status == "failed":
        return current_status in ("queued", "sent")

    return STATUS_ORDER[new_status] > STATUS_ORDER[current_status]


def _apply_status_timestamps(comm: Communication, status: str, timestamp: datetime):
    if status == "sent":
        comm.sent_at = comm.sent_at or timestamp
    elif status == "failed":
        comm.failed_at = comm.failed_at or timestamp
        return

    if STATUS_ORDER[status] >= STATUS_ORDER["delivered"]:
        comm.delivered_at = comm.delivered_at or timestamp
    if STATUS_ORDER[status] >= STATUS_ORDER["opened"]:
        comm.opened_at = comm.opened_at or timestamp
    if STATUS_ORDER[status] >= STATUS_ORDER["read"]:
        comm.read_at = comm.read_at or timestamp
    if STATUS_ORDER[status] >= STATUS_ORDER["clicked"]:
        comm.clicked_at = comm.clicked_at or timestamp
    if STATUS_ORDER[status] >= STATUS_ORDER["converted"]:
        comm.converted_at = comm.converted_at or timestamp


def _apply_counter_delta(campaign: Campaign, old_status: str, new_status: str):
    old_counters = STATUS_COUNTERS.get(old_status, ())
    new_counters = STATUS_COUNTERS.get(new_status, ())

    for counter in old_counters:
        setattr(campaign, counter, max(0, (getattr(campaign, counter) or 0) - 1))
    for counter in new_counters:
        setattr(campaign, counter, (getattr(campaign, counter) or 0) + 1)


def _mark_completed_if_terminal(campaign: Campaign):
    total = campaign.total_recipients or 0
    terminal_count = (campaign.delivered_count or 0) + (campaign.failed_count or 0)
    if total > 0 and terminal_count >= total and campaign.status in ("sending", "sent"):
        campaign.status = "completed"
        campaign.completed_at = campaign.completed_at or datetime.utcnow()


def apply_receipt_transition(
    comm: Communication,
    campaign: Campaign | None,
    receipt: DeliveryReceipt,
) -> bool:
    old_status = comm.status
    if not _should_accept_transition(old_status, receipt.status):
        return False

    timestamp = receipt.timestamp or datetime.utcnow()
    comm.status = receipt.status
    if receipt.status == "failed":
        comm.error_message = receipt.error_message
    _apply_status_timestamps(comm, receipt.status, timestamp)

    if campaign:
        _apply_counter_delta(campaign, old_status, receipt.status)
        _mark_completed_if_terminal(campaign)

    return True


async def process_receipt(
    db: AsyncSession,
    receipt: DeliveryReceipt,
    flush: bool = True,
) -> bool:
    """
    Apply a receipt if it advances the communication lifecycle.
    Returns True when state changed and False for duplicates/out-of-order receipts.
    """
    result = await db.execute(
        select(Communication)
        .where(Communication.id == receipt.communication_id)
        .with_for_update()
    )
    comm = result.scalar_one_or_none()
    if not comm:
        return False

    result = await db.execute(select(Campaign).where(Campaign.id == comm.campaign_id))
    campaign = result.scalar_one_or_none()
    changed = apply_receipt_transition(comm, campaign, receipt)

    if changed and flush:
        await db.flush()
    return changed
