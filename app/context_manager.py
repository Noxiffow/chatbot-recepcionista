"""
WinoWin Recepcionista — Context Manager (Fase 7)

Summarizes long conversation histories to save tokens and keep the AI focused.
When history exceeds MAX_HISTORY_MESSAGES (20), older messages are summarized
using Groq into a 2-3 line summary injected at the start of the prompt.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20  # Messages before summarization kicks in
KEEP_RECENT = 10           # Always keep the last N messages unsummarized


def _format_messages_for_summary(history: list[dict]) -> str:
    """Format a list of message dicts into a readable transcript."""
    lines = []
    for msg in history:
        role = "Cliente" if msg.get("text") else "Recepcionista"
        content = msg.get("text") or msg.get("ai_response") or ""
        if content.strip():
            lines.append(f"{role}: {content.strip()}")
    return "\n".join(lines)


async def summarize_history(
    history: list[dict],
    groq_api_key: str,
    groq_model: str = "llama-3.3-70b-versatile",
) -> str | None:
    """
    Summarize older messages in the conversation history.
    
    Args:
        history: Full conversation history (list of dicts with text/ai_response)
        groq_api_key: Groq API key
        groq_model: Model to use for summarization
        
    Returns:
        A 2-3 line summary string, or None if summarization fails or is not needed.
    """
    if len(history) <= MAX_HISTORY_MESSAGES:
        return None  # No summarization needed
    
    # Keep the most recent messages, summarize the older ones
    older_messages = history[:-KEEP_RECENT]
    if len(older_messages) < 5:
        return None  # Too few to summarize meaningfully
    
    transcript = _format_messages_for_summary(older_messages)
    
    # Build summarization prompt
    summary_prompt = (
        "Eres un asistente que resume conversaciones de WhatsApp entre un cliente "
        "y un recepcionista de peluquería. Resume esta conversación en 2-3 líneas, "
        "capturando: qué servicios preguntó el cliente, si quiere reservar cita, "
        "fechas/horas mencionadas, y el nombre del cliente si lo dijo. "
        "Sé conciso y solo incluye información relevante.\n\n"
        "CONVERSACIÓN:\n"
        f"{transcript}\n\n"
        "RESUMEN (2-3 líneas en español):"
    )
    
    try:
        from groq import AsyncGroq
        
        client = AsyncGroq(api_key=groq_api_key)
        response = await client.chat.completions.create(
            model=groq_model,
            messages=[{"role": "user", "content": summary_prompt}],
            max_tokens=150,
            temperature=0.3,  # Low temperature for factual summary
        )
        summary = response.choices[0].message.content.strip()
        logger.info(
            f"📋 Summarized {len(older_messages)} messages → "
            f"{len(summary)} chars summary"
        )
        return summary
        
    except Exception as e:
        logger.warning(f"⚠️ History summarization failed: {e}")
        # Fallback: generate a simple summary from the context
        return _generate_simple_summary(older_messages)


def _generate_simple_summary(history: list[dict]) -> str:
    """Generate a basic summary without AI (fallback)."""
    services_mentioned = []
    dates_mentioned = []
    client_name = None
    wants_booking = False
    
    for msg in history:
        text = (msg.get("text") or "").lower()
        ai_text = (msg.get("ai_response") or "").lower()
        
        # Check for service mentions
        for keyword in ["alisado", "corte", "brasileño", "queratina", "hialurónico",
                        "taninoplastia", "liso", "orgánico"]:
            if keyword in text and keyword not in services_mentioned:
                services_mentioned.append(keyword)
        
        # Check for date mentions
        for keyword in ["hoy", "mañana", "lunes", "martes", "miércoles", "jueves",
                        "viernes", "sábado", "domingo"]:
            if keyword in text and keyword not in dates_mentioned:
                dates_mentioned.append(keyword)
        
        # Check for booking intent
        if any(kw in text for kw in ["reservar", "cita", "agendar"]):
            wants_booking = True
    
    parts = []
    if services_mentioned:
        parts.append(f"El cliente preguntó sobre: {', '.join(services_mentioned[:3])}")
    if wants_booking:
        parts.append("Quiere reservar una cita")
    if dates_mentioned:
        parts.append(f"Mencionó fechas: {', '.join(dates_mentioned[:3])}")
    if client_name:
        parts.append(f"Nombre: {client_name}")
    
    if not parts:
        return "Conversación inicial sobre servicios de peluquería."
    
    return ". ".join(parts) + "."


async def build_context_for_prompt(
    history: list[dict],
    summary: str | None,
    context: dict | None = None,
) -> str:
    """
    Build the context string to inject at the beginning of the system prompt.
    
    Combines:
    - Conversation summary (if available)
    - Persisted entities from context (last_service_mentioned, etc.)
    
    Returns a string to prepend to the system prompt.
    """
    parts = []
    
    # 1. Summary of older messages
    if summary:
        parts.append(f"[Resumen de la conversación anterior]: {summary}")
    
    # 2. Persisted entities
    if context:
        entity_lines = []
        if context.get("last_service_mentioned"):
            entity_lines.append(
                f"- Último servicio consultado: {context['last_service_mentioned']}"
            )
        if context.get("service_id"):
            entity_lines.append(
                f"- ID del servicio: {context['service_id']}"
            )
        if context.get("last_date_mentioned"):
            entity_lines.append(
                f"- Última fecha mencionada: {context['last_date_mentioned']}"
            )
        if context.get("last_time_mentioned"):
            entity_lines.append(
                f"- Última hora mencionada: {context['last_time_mentioned']}"
            )
        if context.get("client_name"):
            entity_lines.append(
                f"- Nombre del cliente: {context['client_name']}"
            )
        if context.get("booking_confirmed"):
            entity_lines.append("- La reserva está CONFIRMADA")
        
        if entity_lines:
            parts.append("[Entidades recordadas]:\n" + "\n".join(entity_lines))
    
    return "\n\n".join(parts)


def extract_entities_from_message(
    text: str,
    ai_response: str | None = None,
    matched_services: list[dict] | None = None,
) -> dict:
    """
    Extract and return entities from the current message/response.
    
    Returns a dict with any of:
        - last_service_mentioned
        - service_id
        - last_date_mentioned
        - last_time_mentioned
        - client_name
    """
    entities = {}
    text_lower = text.lower()
    
    # Extract service from matched catalog results
    if matched_services and len(matched_services) > 0:
        entities["last_service_mentioned"] = matched_services[0]["name"]
        entities["service_id"] = matched_services[0]["id"]
    
    # Extract date
    from app.webhook_handler import _parse_relative_date
    parsed_date = _parse_relative_date(text)
    if parsed_date:
        entities["last_date_mentioned"] = parsed_date
    
    # Extract time (HH:MM or "a las X")
    import re
    time_match = re.search(r'(\d{1,2}:\d{2})', text)
    if not time_match:
        time_match = re.search(r'a las?\s+(\d{1,2})', text_lower)
    if time_match:
        time_str = time_match.group(1)
        if ":" not in time_str:
            time_str = f"{int(time_str):02d}:00"
        entities["last_time_mentioned"] = time_str
    
    # Extract potential client name (simple heuristic)
    # Look for "me llamo X", "soy X", "mi nombre es X"
    name_match = re.search(
        r'(?:me llamo|soy|mi nombre es)\s+(\w+(?:\s+\w+)?)',
        text_lower
    )
    if name_match:
        name = name_match.group(1).strip().title()
        if len(name) > 2 and name.lower() not in (
            "una", "un", "la", "el", "los", "las", "del", "que", "por",
            "para", "con", "sin", "muy", "mas", "más", "pero", "como",
            "hola", "buenas", "gracias",
        ):
            entities["client_name"] = name
    
    # If the AI response contained the phrase "confirmo tu cita" or similar,
    # it means booking was done
    if ai_response:
        ai_lower = ai_response.lower()
        if any(kw in ai_lower for kw in [
            "cita confirmad", "reserva confirmad", "cita reservad",
            "todo listo", "apuntado", "registrado",
        ]):
            entities["booking_confirmed"] = True
    
    return entities


def merge_context(existing: dict, new_entities: dict) -> dict:
    """Merge new entities into existing context, keeping the most recent values."""
    merged = {**existing}
    for key, value in new_entities.items():
        if value is not None and value != "":
            merged[key] = value
    return merged
