import asyncio
import httpx
import uuid

async def main():
    payload = {
        "communications": [
            {
                "communication_id": str(uuid.uuid4()),
                "recipient": {"name": "Test User", "email": "test@example.com", "phone": "+15555550123"},
                "message": "Hello {{first_name}}, this is a test from XENO.",
                "channel": "whatsapp",
            }
        ],
        "callback_url": "http://127.0.0.1:8000/api/receipts/batch",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post("http://127.0.0.1:8001/channel/send", json=payload)
        print("status:", resp.status_code)
        try:
            print(resp.json())
        except Exception:
            print(resp.text)

if __name__ == "__main__":
    asyncio.run(main())
