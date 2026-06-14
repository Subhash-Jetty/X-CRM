import asyncio
import random
import httpx
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def post_receipts_with_retry(
    client: httpx.AsyncClient,
    callback_url: str,
    receipts: list[dict],
    label: str,
    max_attempts: int = 3,
) -> bool:
    """POST receipt callbacks with bounded exponential backoff."""
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.post(callback_url, json={"receipts": receipts})
            response.raise_for_status()
            return True
        except Exception as e:
            if attempt == max_attempts:
                logger.error(
                    "Failed to send %s callbacks to %s after %s attempts: %s",
                    label,
                    callback_url,
                    max_attempts,
                    e,
                )
                return False

            sleep_for = 0.5 * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
            logger.warning(
                "Retrying %s callbacks to %s after attempt %s failed: %s",
                label,
                callback_url,
                attempt,
                e,
            )
            await asyncio.sleep(sleep_for)


async def simulate_delivery(communications: list[dict], callback_url: str):
    """
    Simulate the full lifecycle of a batch of communications.
    Models real-world channel delivery: sent → delivered/failed → opened → read → clicked → converted.
    Sends receipt callbacks to the CRM asynchronously at each stage.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: Initial "delivered" / "failed" status (immediate network result)
        receipts = []
        for comm in communications:
            # 10% chance of immediate failure (invalid address, network error)
            if random.random() < 0.10:
                receipts.append({
                    "communication_id": comm["communication_id"],
                    "status": "failed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error_message": random.choice([
                        "Invalid recipient address",
                        "Network timeout",
                        "Recipient phone number not on WhatsApp",
                        "Carrier rejected message",
                    ])
                })
            else:
                receipts.append({
                    "communication_id": comm["communication_id"],
                    "status": "delivered",
                    "timestamp": datetime.utcnow().isoformat()
                })

        # Send first batch of receipts. Without this, later engagement callbacks
        # would be confusing, so stop after bounded retries are exhausted.
        if not await post_receipts_with_retry(client, callback_url, receipts, "delivery"):
            return

        # Track delivered for further engagement simulation
        delivered_comms = [r for r in receipts if r["status"] == "delivered"]

        # Step 2: Simulate Opens (60% of delivered open the message)
        await asyncio.sleep(random.uniform(2.0, 5.0))
        open_receipts = []
        opened_comms = []
        for r in delivered_comms:
            if random.random() < 0.60:
                opened_comms.append(r)
                open_receipts.append({
                    "communication_id": r["communication_id"],
                    "status": "opened",
                    "timestamp": datetime.utcnow().isoformat()
                })

        if open_receipts:
            await post_receipts_with_retry(client, callback_url, open_receipts, "open")

        # Step 3: Simulate Reads (70% of opened actually read the full message)
        await asyncio.sleep(random.uniform(1.0, 3.0))
        read_receipts = []
        read_comms = []
        for r in opened_comms:
            if random.random() < 0.70:
                read_comms.append(r)
                read_receipts.append({
                    "communication_id": r["communication_id"],
                    "status": "read",
                    "timestamp": datetime.utcnow().isoformat()
                })

        if read_receipts:
            await post_receipts_with_retry(client, callback_url, read_receipts, "read")

        # Step 4: Simulate Clicks (30% of readers click the CTA link)
        await asyncio.sleep(random.uniform(1.0, 4.0))
        click_receipts = []
        clicked_comms = []
        for r in read_comms:
            if random.random() < 0.30:
                clicked_comms.append(r)
                click_receipts.append({
                    "communication_id": r["communication_id"],
                    "status": "clicked",
                    "timestamp": datetime.utcnow().isoformat()
                })

        if click_receipts:
            await post_receipts_with_retry(client, callback_url, click_receipts, "click")

        # Step 5: Simulate Conversions / Orders (20% of clickers place an order)
        # This models "order came because of this communication" — attribution tracking
        await asyncio.sleep(random.uniform(2.0, 6.0))
        conversion_receipts = []
        for r in clicked_comms:
            if random.random() < 0.20:
                conversion_receipts.append({
                    "communication_id": r["communication_id"],
                    "status": "converted",
                    "timestamp": datetime.utcnow().isoformat()
                })

        if conversion_receipts:
            await post_receipts_with_retry(client, callback_url, conversion_receipts, "conversion")
