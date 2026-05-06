import logging
import httpx
from app.config import FACEBOOK_PAGE_ACCESS_TOKEN

logger = logging.getLogger(__name__)
MESSENGER_API_URL = "https://graph.facebook.com/v20.0/me/messages"


async def send_message(recipient_id: str, text: str):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    params = {"access_token": FACEBOOK_PAGE_ACCESS_TOKEN}

    async with httpx.AsyncClient() as client:
        response = await client.post(MESSENGER_API_URL, json=payload, params=params)
        if not response.is_success:
            logger.error(f"Facebook API error {response.status_code}: {response.text}")
        response.raise_for_status()
        return response.json()


async def send_typing_on(recipient_id: str):
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": "typing_on",
    }
    params = {"access_token": FACEBOOK_PAGE_ACCESS_TOKEN}

    async with httpx.AsyncClient() as client:
        await client.post(MESSENGER_API_URL, json=payload, params=params)


async def send_typing_off(recipient_id: str):
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": "typing_off",
    }
    params = {"access_token": FACEBOOK_PAGE_ACCESS_TOKEN}

    async with httpx.AsyncClient() as client:
        await client.post(MESSENGER_API_URL, json=payload, params=params)
