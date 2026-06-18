"""
WinoWin Recepcionista — Groq AI Client
"""
import logging
import time
from typing import Any

from groq import AsyncGroq

from app.config import config

logger = logging.getLogger(__name__)


async def generate_response(
    user_message: str,
    conversation_history: list[dict] | None = None,
    business_type: str | None = None,
    catalog_services: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Generate an AI response using Groq (llama-3.3-70b).

    Returns a dict with:
        - response: the generated text
        - model: model used
        - tokens_used: total tokens
        - latency_ms: time taken in ms
        - error: error message if failed
    """
    result = {
        "response": None,
        "model": config.groq_model,
        "tokens_used": 0,
        "latency_ms": 0,
        "error": None,
    }

    if not config.groq_enabled:
        result["error"] = "GROQ_API_KEY not configured"
        logger.warning("⚠️ Groq not configured — returning fallback")
        result["response"] = (
            "¡Hola! Soy el recepcionista virtual de {name}. "
            "¿En qué puedo ayudarte? (IA no configurada)".format(
                name=config.business_name
            )
        )
        return result

    from app.prompts import build_messages

    messages = build_messages(user_message, conversation_history, catalog_services)

    logger.info(f"🤖 Calling Groq with model={config.groq_model}, "
                f"messages_count={len(messages)}")

    start_time = time.monotonic()

    try:
        client = AsyncGroq(api_key=config.groq_api_key)
        response = await client.chat.completions.create(
            model=config.groq_model,
            messages=messages,
            max_tokens=config.groq_max_tokens,
            temperature=config.groq_temperature,
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        result["latency_ms"] = elapsed_ms

        choice = response.choices[0]
        result["response"] = choice.message.content
        result["tokens_used"] = response.usage.total_tokens if response.usage else 0

        logger.info(
            f"✅ Groq response in {elapsed_ms}ms, "
            f"tokens={result['tokens_used']}: "
            f"{result['response'][:80]}..."
        )

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        result["latency_ms"] = elapsed_ms
        result["error"] = str(e)
        logger.exception(f"❌ Groq API error after {elapsed_ms}ms: {e}")
        result["response"] = (
            "Lo siento, estoy teniendo dificultades técnicas. "
            "¿Podrías intentarlo de nuevo en un momento? "
            "Si es urgente, llámanos al +34 900 123 456."
        )

    return result
