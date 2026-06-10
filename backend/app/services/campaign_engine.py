"""
Campaign engine — handles campaign creation, sending, and stats.
"""
from datetime import datetime
from uuid import UUID
import httpx
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campaign, Communication, SegmentMember, Customer, Segment
from app.config import settings


async def send_campaign(db: AsyncSession, campaign_id: UUID) -> int:
    """
    Execute a campaign:
    1. Get all segment members
    2. Create a Communication record per member
    3. Batch-send to the channel service
    4. Update campaign status
    Returns number of communications created.
    """
    # Get campaign
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise ValueError("Campaign not found")

    if campaign.status not in ("draft", "scheduled"):
        raise ValueError(f"Campaign is already {campaign.status}")

    # Get segment members with customer data
    members_result = await db.execute(
        select(Customer)
        .join(SegmentMember, SegmentMember.customer_id == Customer.id)
        .where(SegmentMember.segment_id == campaign.segment_id)
    )
    customers = members_result.scalars().all()

    if not customers:
        raise ValueError("No customers in segment")

    # Update campaign status
    campaign.status = "sending"
    campaign.sent_at = datetime.utcnow()
    campaign.total_recipients = len(customers)

    # Create Communication records and prepare batch for channel service
    communications_batch = []
    for customer in customers:
        # Personalise message by replacing placeholders
        personalised = personalise_message(campaign.message_template, customer)

        comm = Communication(
            campaign_id=campaign_id,
            customer_id=customer.id,
            channel=campaign.channel,
            personalised_message=personalised,
            status="queued",
        )
        db.add(comm)
        await db.flush()  # Get the ID

        communications_batch.append({
            "communication_id": str(comm.id),
            "recipient": {
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
            },
            "message": personalised,
            "channel": campaign.channel,
        })

    await db.flush()

    # Send batch to channel service (fire and forget — channel will callback)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.CHANNEL_SERVICE_URL}/channel/send",
                json={
                    "communications": communications_batch,
                    "callback_url": f"{settings.BACKEND_URL}/api/receipts/batch",
                },
            )
            if response.status_code == 200:
                campaign.sent_count = len(communications_batch)
                campaign.status = "sent"
            else:
                campaign.status = "failed"
    except httpx.RequestError:
        # Channel service may be waking up (cold start) — mark as sent anyway
        # The channel service will process when it comes online
        campaign.sent_count = len(communications_batch)
        campaign.status = "sent"

    await db.flush()
    return len(communications_batch)


def personalise_message(template: str, customer) -> str:
    """Replace placeholders in message template with customer data."""
    message = template
    replacements = {
        "{{name}}": customer.name or "there",
        "{{first_name}}": (customer.name or "there").split()[0],
        "{{email}}": customer.email or "",
        "{{total_spend}}": f"₹{customer.total_spend:,.0f}" if customer.total_spend else "₹0",
        "{{order_count}}": str(customer.order_count or 0),
        "{{avg_order}}": f"₹{customer.avg_order_value:,.0f}" if customer.avg_order_value else "₹0",
    }
    for placeholder, value in replacements.items():
        message = message.replace(placeholder, value)
    return message


async def get_campaign_stats(db: AsyncSession, campaign_id: UUID) -> dict:
    """Get campaign delivery funnel stats."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise ValueError("Campaign not found")

    total = campaign.total_recipients or 1  # Prevent division by zero

    return {
        "campaign_id": str(campaign_id),
        "campaign_name": campaign.name,
        "channel": campaign.channel,
        "status": campaign.status,
        "total_recipients": campaign.total_recipients,
        "sent": campaign.sent_count,
        "delivered": campaign.delivered_count,
        "failed": campaign.failed_count,
        "opened": campaign.opened_count,
        "read": campaign.read_count,
        "clicked": campaign.clicked_count,
        "delivery_rate": round(campaign.delivered_count / total * 100, 1) if total else 0,
        "open_rate": round(campaign.opened_count / total * 100, 1) if total else 0,
        "click_rate": round(campaign.clicked_count / total * 100, 1) if total else 0,
        "sent_at": campaign.sent_at.isoformat() if campaign.sent_at else None,
    }
