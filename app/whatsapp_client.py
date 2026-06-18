"""
WinoWin Recepcionista — WhatsApp Cloud API Client
"""
import logging
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger(__name__)


async def check_health() -> dict[str, Any]:
    """
    Check the WABA health status.
    Returns the health_assurance response from Meta.
    """
    if not config.whatsapp_token:
        return {"error": "WHATSAPP_TOKEN not configured", "can_send_message": False}

    url = config.health_api_url
    headers = {
        "Authorization": f"Bearer {config.whatsapp_token}",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            logger.info(f"🏥 Health check: {resp.status_code} — {resp.text[:300]}")
            return resp.json()
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {"error": str(e), "can_send_message": False}


async def send_message(
    to: str,
    text: str,
    preview_url: bool = False,
) -> dict[str, Any]:
    """
    Send a WhatsApp text message via the Meta Cloud API.

    NOTE: Currently BLOCKED by Meta (payment method required).
    This function is ready for when the block is lifted.
    """
    result = {
        "success": False,
        "to": to,
        "text": text[:100],
        "status_code": None,
        "response": None,
        "error": None,
    }

    if not config.whatsapp_token:
        result["error"] = "WHATSAPP_TOKEN not configured"
        logger.warning(f"⚠️ Cannot send message: {result['error']}")
        return result

    url = config.messages_api_url
    headers = {
        "Authorization": f"Bearer {config.whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": preview_url, "body": text},
    }

    logger.info(f"📤 Sending message to {to}: {text[:80]}...")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            result["status_code"] = resp.status_code
            result["response"] = resp.json()

            if resp.status_code == 200:
                result["success"] = True
                logger.info(f"✅ Message sent to {to}")
            else:
                result["error"] = resp.text
                logger.error(f"❌ Failed to send message ({resp.status_code}): {resp.text}")
        except Exception as e:
            result["error"] = str(e)
            logger.exception(f"❌ Exception sending message: {e}")

    return result


async def mark_as_read(message_id: str) -> bool:
    """Mark an incoming message as read."""
    if not config.whatsapp_token:
        return False

    url = f"{config.graph_api_base}/{config.graph_api_version}/{config.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {config.whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            return resp.status_code == 200
        except Exception:
            return False
