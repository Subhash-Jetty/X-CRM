"""
Campaign engine: campaign creation, dispatch, personalization, and stats.
"""
from datetime import datetime
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Campaign, Communication, Customer, SegmentMember


class CampaignDispatchError(RuntimeError):
    """Raised when the CRM cannot hand a campaign batch to the channel service."""

    def __init__(self, message: str, recipient_count: int = 0):
        super().__init__(message)
        self.recipient_count = recipient_count


async def send_campaign(db: AsyncSession, campaign_id: UUID) -> int:
    """
    Execute a campaign by creating per-recipient communication rows and handing
    them to the separate channel service. If dispatch fails, the campaign is
    marked failed and the caller gets an explicit error instead of false success.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise ValueError("Campaign not found")

    if campaign.status not in ("draft", "scheduled"):
        raise ValueError(f"Campaign is already {campaign.status}")

    members_result = await db.execute(
        select(Customer)
        .join(SegmentMember, SegmentMember.customer_id == Customer.id)
        .where(SegmentMember.segment_id == campaign.segment_id)
    )
    customers = members_result.scalars().all()
    if not customers:
        raise ValueError("No customers in segment")

    handoff_time = datetime.utcnow()
    campaign.status = "sending"
    campaign.sent_at = handoff_time
    campaign.total_recipients = len(customers)

    communications = []
    communications_batch = []
    for customer in customers:
        personalised = personalise_message(campaign.message_template, customer)
        comm = Communication(
            id=uuid4(),
            campaign_id=campaign_id,
            customer_id=customer.id,
            channel=campaign.channel,
            personalised_message=personalised,
            status="sent",
            sent_at=handoff_time,
        )
        db.add(comm)
        communications.append(comm)
        communications_batch.append(
            {
                "communication_id": str(comm.id),
                "recipient": {
                    "name": customer.name,
                    "email": customer.email,
                    "phone": customer.phone,
                },
                "message": personalised,
                "channel": campaign.channel,
            }
        )

    await db.flush()
    await db.commit()

    dispatch_error = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.CHANNEL_SERVICE_URL}/channel/send",
                json={
                    "communications": communications_batch,
                    "callback_url": f"{settings.BACKEND_URL}/api/receipts/batch",
                },
            )
        if 200 <= response.status_code < 300:
            campaign.sent_count = len(communications_batch)
            campaign.status = "sent"
        else:
            campaign.status = "failed"
            campaign.failed_count = len(communications)
            for comm in communications:
                comm.status = "failed"
                comm.failed_at = datetime.utcnow()
                comm.error_message = f"Channel service rejected dispatch with HTTP {response.status_code}"
            dispatch_error = (
                f"Channel service rejected dispatch with HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )
    except httpx.RequestError as exc:
        campaign.status = "failed"
        campaign.failed_count = len(communications)
        for comm in communications:
            comm.status = "failed"
            comm.failed_at = datetime.utcnow()
            comm.error_message = f"Channel service unreachable: {exc}"
        dispatch_error = f"Channel service unreachable: {exc}"

    await db.flush()
    if dispatch_error:
        raise CampaignDispatchError(dispatch_error, len(communications_batch))

    return len(communications_batch)


def personalise_message(template: str, customer) -> str:
    """Replace supported placeholders in a message template."""
    message = template
    replacements = {
        "{{name}}": customer.name or "there",
        "{{first_name}}": (customer.name or "there").split()[0],
        "{{email}}": customer.email or "",
        "{{total_spend}}": f"Rs.{customer.total_spend:,.0f}" if customer.total_spend else "Rs.0",
        "{{order_count}}": str(customer.order_count or 0),
        "{{avg_order}}": f"Rs.{customer.avg_order_value:,.0f}" if customer.avg_order_value else "Rs.0",
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

    total = campaign.total_recipients or 1

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
        "converted": campaign.converted_count or 0,
        "delivery_rate": round(campaign.delivered_count / total * 100, 1) if total else 0,
        "open_rate": round(campaign.opened_count / total * 100, 1) if total else 0,
        "click_rate": round(campaign.clicked_count / total * 100, 1) if total else 0,
        "conversion_rate": round((campaign.converted_count or 0) / total * 100, 1) if total else 0,
        "sent_at": campaign.sent_at.isoformat() if campaign.sent_at else None,
    }
