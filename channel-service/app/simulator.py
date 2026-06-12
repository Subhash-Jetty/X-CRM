import asyncio
import random
import httpx
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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

        # Send first batch of receipts
        try:
            await client.post(callback_url, json={"receipts": receipts})
        except Exception as e:
            logger.error(f"Failed to send delivery callback to {callback_url}: {e}")
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
            try:
                await client.post(callback_url, json={"receipts": open_receipts})
            except Exception as e:
                logger.error(f"Failed to send open callbacks: {e}")

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
            try:
                await client.post(callback_url, json={"receipts": read_receipts})
            except Exception as e:
                logger.error(f"Failed to send read callbacks: {e}")

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
            try:
                await client.post(callback_url, json={"receipts": click_receipts})
            except Exception as e:
                logger.error(f"Failed to send click callbacks: {e}")

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
            try:
                await client.post(callback_url, json={"receipts": conversion_receipts})
            except Exception as e:
                logger.error(f"Failed to send conversion callbacks: {e}")
