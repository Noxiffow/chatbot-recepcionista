"""
WinoWin Recepcionista — Webhook Message Parser & Processor
"""
import json
import logging
import re
from datetime import datetime, timezone, date, timedelta
from typing import Any

import aiosqlite

from app.config import config
from app.database import (
    save_incoming_message,
    save_ai_response,
    update_message_status,
    update_or_create_conversation,
    get_conversation_history,
    get_conversation,
    update_conversation_state,
    update_conversation_context,
    close_conversation,
    search_services,
    get_all_categories,
    get_available_slots,
    get_available_dates,
    book_appointment,
    generate_slots,
)
from app.groq_client import generate_response
from app.whatsapp_client import send_message, mark_as_read
from app.conversation_state import (
    SERVICE_KEYWORDS,
    BOOKING_KEYWORDS,
    _is_service_query,
    _is_booking_intent,
    detect_handoff,
    detect_frustration,
    detect_intent,
    compute_next_state,
    get_state_instructions,
    ConversationState,
)
from app.context_manager import (
    summarize_history,
    build_context_for_prompt,
    extract_entities_from_message,
    merge_context,
    MAX_HISTORY_MESSAGES,
)

logger = logging.getLogger(__name__)

# ── Message parsing ────────────────────────────────────────


def parse_webhook_body(body: dict) -> list[dict]:
    """
    Parse a Meta webhook POST body and extract all messages.

    Returns a list of parsed message dicts, each with:
        - wa_message_id: WhatsApp message ID (wamid)
        - from_number: sender phone number
        - to_number: business number (optional)
        - text: message body text (optional, None for media-only)
        - media_type: "text", "image", "audio", "video", "document", "location", etc.
        - media_url: media URL if present
        - timestamp_wa: original WhatsApp timestamp
        - raw: the original value dict from the webhook
    """
    messages = []

    try:
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})

                # Check for status updates (delivered, read, failed)
                statuses = value.get("statuses", [])
                for status in statuses:
                    logger.info(
                        f"📊 Status update: {status.get('status')} "
                        f"for msg {status.get('id')} "
                        f"to {status.get('recipient_id')}"
                    )

                # Check for messages
                raw_messages = value.get("messages", [])
                contacts = value.get("contacts", [])

                # Build contact lookup
                contact_map = {c.get("wa_id"): c.get("profile", {}).get("name", "")
                               for c in contacts}

                for msg in raw_messages:
                    msg_type = msg.get("type", "unknown")
                    parsed = {
                        "wa_message_id": msg.get("id", ""),
                        "from_number": msg.get("from", "desconocido"),
                        "to_number": config.phone_number_id,
                        "text": None,
                        "media_type": msg_type,
                        "media_url": None,
                        "timestamp_wa": msg.get("timestamp", ""),
                        "contact_name": contact_map.get(msg.get("from", ""), ""),
                        "raw": value,
                    }

                    # Extract text or media
                    if msg_type == "text":
                        parsed["text"] = msg.get("text", {}).get("body", "")
                    elif msg_type == "image":
                        parsed["media_url"] = msg.get("image", {}).get("link")
                        parsed["text"] = msg.get("image", {}).get("caption", "")
                    elif msg_type == "audio":
                        parsed["media_url"] = msg.get("audio", {}).get("link")
                    elif msg_type == "video":
                        parsed["media_url"] = msg.get("video", {}).get("link")
                        parsed["text"] = msg.get("video", {}).get("caption", "")
                    elif msg_type == "document":
                        parsed["media_url"] = msg.get("document", {}).get("link")
                        parsed["text"] = msg.get("document", {}).get("caption", "")
                    elif msg_type == "location":
                        loc = msg.get("location", {})
                        parsed["text"] = (
                            f"📍 Ubicación: lat={loc.get('latitude')}, "
                            f"lon={loc.get('longitude')}"
                        )
                    elif msg_type in ("reaction", "interactive", "button", "order"):
                        # Handle interactive messages
                        interactive = msg.get(msg_type, {})
                        parsed["text"] = json.dumps(interactive) if interactive else msg_type

                    messages.append(parsed)
                    logger.info(
                        f"📩 Parsed {msg_type} message from {parsed['from_number']}: "
                        f"{str(parsed.get('text', ''))[:80]}"
                    )

    except Exception as e:
        logger.exception(f"❌ Error parsing webhook body: {e}")

    return messages


# ── Message processing pipeline ─────────────────────────────

# Spanish day names for relative date parsing (unique to webhook_handler)
DAY_NAMES = {
    "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
    "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
}
DAY_NAMES_PLURAL = {
    "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
    "jueves": 3, "viernes": 4, "sábados": 5, "sabados": 5, "domingos": 6,
}


def _parse_relative_date(text: str) -> str | None:
    """Try to extract a date reference from the message and return YYYY-MM-DD.
    Supports: 'hoy', 'mañana', 'pasado mañana', day names (lunes, martes...),
    and explicit YYYY-MM-DD or DD/MM/YYYY formats.
    Returns None if no date found.
    """
    text_lower = text.lower()
    today = date.today()

    # Check longer phrases first to avoid partial matches
    # Relative: pasado mañana (2 days from now)
    if re.search(r'\bpasado\s+mañana\b', text_lower):
        return (today + timedelta(days=2)).isoformat()

    # Relative: mañana
    if re.search(r'\bmañana\b', text_lower):
        return (today + timedelta(days=1)).isoformat()

    # Relative: hoy
    if re.search(r'\bhoy\b', text_lower):
        return today.isoformat()

    # Day names: "el lunes", "el próximo viernes", "este martes"
    for day_name, day_num in {**DAY_NAMES, **DAY_NAMES_PLURAL}.items():
        pattern = rf'\b(?:el\s+)?{day_name}\b'
        if re.search(pattern, text_lower):
            # Check if it says "próximo" or "que viene" — next week
            is_next = bool(re.search(r'\b(?:próximo|proximo|que\s+viene)\b', text_lower))
            days_until = (day_num - today.weekday()) % 7
            if days_until == 0 and not is_next:
                days_until = 0  # Today
            elif days_until == 0:
                days_until = 7  # Next week
            target_date = today + timedelta(days=days_until)
            return target_date.isoformat()

    # Explicit YYYY-MM-DD
    m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # Explicit DD/MM/YYYY or DD/MM
    m = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b', text)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    return None


def _format_availability_for_prompt(
    service_name: str,
    duration_min: int,
    date_str: str,
    available_slots: list[dict],
) -> str:
    """Format availability info to inject into the AI prompt."""
    if not available_slots:
        return (
            f"\n\n[MENSAJE DEL SISTEMA — DISPONIBILIDAD REAL]\n"
            f"El cliente quiere reservar '{service_name}' (dura {duration_min} min) "
            f"para el {date_str}. He comprobado la agenda real y NO HAY HUECOS "
            f"disponibles para ese día. NO inventes disponibilidad. Dile al cliente "
            f"que no hay citas libres para ese día y ofrécele consultar otros días. "
            f"Pregúntale qué otro día le vendría bien.\n"
        )

    slots_text = []
    for slot in available_slots[:8]:  # Max 8 slots to show
        slots_text.append(f"  - {slot['start_time']} a {slot['end_time']}")

    return (
        f"\n\n[MENSAJE DEL SISTEMA — DISPONIBILIDAD REAL]\n"
        f"El cliente quiere reservar '{service_name}' (dura {duration_min} min) "
        f"para el {date_str}. He comprobado la agenda real y estos son los "
        f"ÚNICOS huecos disponibles:\n"
        + "\n".join(slots_text) +
        f"\n\nIMPORTANTE: Solo puedes ofrecer estos horarios concretos. "
        f"NO inventes otros horarios. Pregunta al cliente cuál prefiere y "
        f"pide confirmación antes de reservar. Si el cliente confirma, "
        f"dile 'Perfecto, voy a confirmar tu reserva ahora mismo'.\n"
    )


async def _handle_booking_intent(
    db: aiosqlite.Connection,
    text: str,
    from_number: str,
) -> str | None:
    """
    Process a booking intent message. Queries real availability from DB
    and returns a context string to inject into the AI prompt.
    Returns None if no service/date could be determined.
    """
    text_lower = text.lower()

    # Try to find a date in the message
    target_date = _parse_relative_date(text)

    # Search for matching service
    search_query = _is_service_query(text)
    if not search_query:
        # Try broader search with just the text
        search_query = text_lower

    catalog_services = await search_services(db, search_query)
    if not catalog_services:
        logger.info(f"📅 Booking intent but no matching service found for '{search_query}'")
        return None

    # Use the first match as the most likely
    service = catalog_services[0]
    service_name = service["name"]
    duration_min = service["duration_min"]

    logger.info(
        f"📅 Booking intent detected: service='{service_name}', "
        f"duration={duration_min}min, date_hint='{target_date}'"
    )

    # If we have a date, check real availability
    if target_date:
        available_slots = await get_available_slots(db, target_date, duration_min)
        return _format_availability_for_prompt(
            service_name, duration_min, target_date, available_slots
        )

    # No date specified — search next 7 days for availability
    available_dates = await get_available_dates(db, duration_min, limit=5)

    if available_dates:
        dates_text = "\n".join(
            f"  - {d['date']} ({d['weekday']}): primer hueco a las {d['first_available']}"
            for d in available_dates
        )
        return (
            f"\n\n[MENSAJE DEL SISTEMA — DISPONIBILIDAD REAL]\n"
            f"El cliente quiere reservar '{service_name}' (dura {duration_min} min) "
            f"pero no ha especificado fecha. He comprobado la agenda real y estos son "
            f"los próximos días con disponibilidad:\n"
            f"{dates_text}\n\n"
            f"IMPORTANTE: Solo puedes ofrecer estos días y horarios. "
            f"NO inventes disponibilidad. Pregunta al cliente qué día le viene bien.\n"
        )

    return (
        f"\n\n[MENSAJE DEL SISTEMA — DISPONIBILIDAD REAL]\n"
        f"El cliente quiere reservar '{service_name}' (dura {duration_min} min). "
        f"He comprobado la agenda y NO hay disponibilidad en los próximos 30 días. "
        f"Dile al cliente que lo sientes y que puede llamar al +34 900 123 456 "
        f"para consultar cancelaciones.\n"
    )


async def _try_confirm_booking(
    db: aiosqlite.Connection,
    text: str,
    from_number: str,
    history: list[dict],
) -> str | None:
    """
    Check if the user is confirming a booking from a previous offer.
    Looks at the last assistant message to see what was offered.
    Returns a confirmation message or None if nothing to confirm.
    """
    text_lower = text.lower().strip()

    # Confirmation keywords
    confirm_keywords = [
        "sí", "si", "ok", "vale", "genial", "perfecto", "de acuerdo",
        "confirmo", "confirmar", "reservalo", "resérvalo", "reservalo",
        "adelante", "venga", "dale", "claro", "por supuesto",
        "10:00", "10:30", "11:00", "11:30", "12:00", "12:30",
        "16:00", "16:30", "17:00", "17:30", "18:00", "18:30",
        "19:00", "19:30", "09:00", "09:30",
    ]

    # Check if it looks like a confirmation (short message with keyword or time)
    is_confirmation = False
    for kw in confirm_keywords:
        if text_lower == kw or text_lower.startswith(kw) or kw in text_lower.split():
            is_confirmation = True
            break

    # Also check if it's just a time (like "10:00" or "a las 10")
    if re.match(r'^\d{1,2}[:h]\d{2}$', text_lower.strip()):
        is_confirmation = True
    if re.match(r'^(a las?\s+)?\d{1,2}[:h]\d{2}', text_lower.strip()):
        is_confirmation = True

    if not is_confirmation:
        return None

    # Look at the last assistant message for availability context
    last_assistant_msg = None
    for msg in reversed(history):
        if msg.get("ai_response"):
            last_assistant_msg = msg["ai_response"]
            break

    if not last_assistant_msg:
        return None

    # Check if the last assistant message contained availability info
    if "DISPONIBILIDAD REAL" not in last_assistant_msg:
        return None

    # Extract the service and date from the last assistant message
    # (This is a simplification — we'd need full context tracking for production)
    # For now, return a note that the system should book
    return (
        f"\n\n[MENSAJE DEL SISTEMA — CONFIRMACIÓN DE RESERVA]\n"
        f"El cliente ha confirmado que quiere la cita. El mensaje del cliente fue: '{text}'. "
        f"DILE al cliente: '¡Perfecto! Te confirmo la cita. ¿Me dices tu nombre completo "
        f"para la reserva?' NO reserves aún sin el nombre. Pide el nombre primero.\n"
    )


async def process_message(
    db: aiosqlite.Connection,
    parsed_msg: dict,
    try_send: bool = False,
) -> dict:
    """
    Full processing pipeline for an incoming message:
    1. Save to database
    2. Update/create conversation (Fase 7: with 24h timeout)
    3. Load conversation state & persisted context
    4. Detect intent → update state machine
    5. Handle HANDOFF/COMPLAINT specially
    6. Check for booking intent → query real availability
    7. Extract entities → persist context
    8. Summarize long history (context manager)
    9. Generate AI response (if Groq configured)
    10. Save AI response
    11. Optionally send response

    Returns processing result dict.
    """
    result = {
        "message_id": None,
        "conversation_id": None,
        "ai_response": None,
        "ai_model": None,
        "ai_tokens": 0,
        "ai_latency_ms": 0,
        "sent": False,
        "error": None,
        "new_state": None,
    }

    from_number = parsed_msg["from_number"]
    text = parsed_msg.get("text") or ""

    # Skip empty messages (e.g., media-only without caption)
    if not text.strip() and parsed_msg["media_type"] != "text":
        logger.info(f"⏭️ Skipping empty message from {from_number}")
        pass

    try:
        # 1. Save incoming message
        msg_id = await save_incoming_message(
            db=db,
            wa_message_id=parsed_msg["wa_message_id"],
            from_number=from_number,
            text=text if text.strip() else None,
            to_number=parsed_msg.get("to_number"),
            media_type=parsed_msg["media_type"],
            media_url=parsed_msg.get("media_url"),
            timestamp_wa=parsed_msg.get("timestamp_wa"),
            raw_payload=parsed_msg.get("raw"),
        )
        result["message_id"] = msg_id

        # 2. Update/create conversation (Fase 7: with 24h timeout)
        conv_id = await update_or_create_conversation(db, from_number)
        result["conversation_id"] = conv_id

        # 3. Mark as read
        await mark_as_read(parsed_msg["wa_message_id"])

        # ─── FASE 7: Load conversation state & context ───
        conv = await get_conversation(db, from_number)
        current_state = conv["state"] if conv else ConversationState.IDLE
        persisted_context = conv["context"] if conv else {}
        logger.info(f"📊 Conversation {conv_id} state={current_state}, context={persisted_context}")

        # ─── FASE 7: Detect intent & update state ───
        detected_intent = "unknown"
        if text.strip():
            detected_intent = detect_intent(text, current_state, persisted_context)

        # Compute next state
        new_state = compute_next_state(current_state, detected_intent, persisted_context)
        if new_state != current_state:
            await update_conversation_state(db, conv_id, new_state)
            result["new_state"] = new_state
            current_state = new_state
            logger.info(f"🔄 State transition: {current_state} (intent={detected_intent})")

        # ─── FASE 7: Handle HANDOFF and COMPLAINT ───
        if current_state in (ConversationState.HANDOFF, ConversationState.COMPLAINT):
            # Special handling for handoff/complaint
            if current_state == ConversationState.HANDOFF:
                result["ai_response"] = (
                    "Entendido. Voy a pasar tu consulta a un compañero/a ahora mismo. "
                    "Te atenderá en breve. Mientras tanto, puedes llamarnos al +34 900 123 456 "
                    "si es urgente. ¡Gracias por tu paciencia! 🙏"
                )
                await close_conversation(db, conv_id, "handed_off")
            elif current_state == ConversationState.COMPLAINT:
                result["ai_response"] = (
                    "Lamento mucho las molestias. Para poder resolver tu caso de la mejor manera, "
                    "voy a pasar tu consulta a un compañero/a que te atenderá personalmente. "
                    "¿Me confirmas si quieres que te derive ya?"
                )
                # Don't close yet — let user confirm handoff

            # Save and send handoff/complaint response
            await save_ai_response(
                db=db,
                message_id=msg_id,
                ai_response=result["ai_response"],
                ai_model="default",
                ai_tokens_used=0,
                ai_latency_ms=0,
            )
            if try_send and result["ai_response"]:
                send_result = await send_message(from_number, result["ai_response"])
                result["sent"] = send_result.get("success", False)

            return result

        # 4. Get conversation history for context
        history = await get_conversation_history(db, from_number, limit=MAX_HISTORY_MESSAGES)

        # ─── FASE 7: Context summarization ───
        summary = None
        if len(history) > MAX_HISTORY_MESSAGES:
            logger.info(f"📋 History has {len(history)} messages — summarizing...")
            if config.groq_enabled:
                summary = await summarize_history(
                    history, config.groq_api_key, config.groq_model
                )
            else:
                from app.context_manager import _generate_simple_summary
                summary = _generate_simple_summary(history[:-10])

        # Build context block for the prompt
        context_block = await build_context_for_prompt(
            history, summary, persisted_context
        )

        # 5. Query catalog for service-related queries
        catalog_services = None
        booking_context = None

        if text.strip():
            search_query = _is_service_query(text)
            if search_query:
                logger.info(f"🔍 Service query detected, searching catalog: '{search_query}'")
                catalog_services = await search_services(db, search_query)
                if catalog_services:
                    logger.info(
                        f"📋 Found {len(catalog_services)} matching services: "
                        f"{[s['name'][:40] for s in catalog_services]}"
                    )
                else:
                    logger.info("📋 No specific match, loading all categories for context")
                    catalog_services = await search_services(db, "")

            # Check for booking intent
            if _is_booking_intent(text):
                logger.info("📅 Booking intent detected, checking real availability...")
                booking_context = await _handle_booking_intent(
                    db, text, from_number
                )
            else:
                # Check if user is confirming a previously offered slot
                booking_context = await _try_confirm_booking(
                    db, text, from_number, history
                )

        # ─── FASE 7: Extract entities from message ───
        new_entities = {}
        if text.strip():
            new_entities = extract_entities_from_message(
                text,
                ai_response=result.get("ai_response"),
                matched_services=catalog_services,
            )

        # Merge with existing context and persist
        if new_entities:
            merged_context = merge_context(persisted_context, new_entities)
            if merged_context != persisted_context:
                await update_conversation_context(db, conv_id, merged_context)
                persisted_context = merged_context

        # 6. Generate AI response
        if text.strip():
            # Build effective message with state instructions + context + booking info
            effective_message = text

            # Add state instructions
            state_instructions = get_state_instructions(current_state)
            if state_instructions:
                effective_message = (
                    f"[INSTRUCCIONES DE ESTADO]: {state_instructions}\n\n"
                    f"{effective_message}"
                )

            # Add context block (summary + entities)
            if context_block:
                effective_message = (
                    f"[CONTEXTO]:\n{context_block}\n\n"
                    f"{effective_message}"
                )

            # Append booking context if available
            if booking_context:
                effective_message = effective_message + booking_context
                logger.info(
                    f"📅 Injected availability context: "
                    f"{booking_context[:120].replace(chr(10), ' ')}..."
                )

            ai_result = await generate_response(
                user_message=effective_message,
                conversation_history=history,
                catalog_services=catalog_services,
            )
            result["ai_response"] = ai_result.get("response")
            result["ai_model"] = ai_result.get("model")
            result["ai_tokens"] = ai_result.get("tokens_used", 0)
            result["ai_latency_ms"] = ai_result.get("latency_ms", 0)

            if ai_result.get("error"):
                result["error"] = ai_result["error"]
                await update_message_status(db, msg_id, "failed", ai_result["error"])
            else:
                # Save AI response
                await save_ai_response(
                    db=db,
                    message_id=msg_id,
                    ai_response=result["ai_response"],
                    ai_model=result["ai_model"],
                    ai_tokens_used=result["ai_tokens"],
                    ai_latency_ms=result["ai_latency_ms"],
                )

                # 7. Send response (if enabled and unblocked)
                if try_send and result["ai_response"]:
                    send_result = await send_message(from_number, result["ai_response"])
                    result["sent"] = send_result.get("success", False)
                    if result["sent"]:
                        await update_message_status(db, msg_id, "responded")
                    elif send_result.get("status_code") == 400:
                        await update_message_status(
                            db, msg_id, "processed",
                            f"Send blocked: {send_result.get('error', '')[:200]}"
                        )

        else:
            logger.info(f"📎 Media message from {from_number} — no text to process")
            result["ai_response"] = (
                "¡Gracias! He recibido tu archivo. "
                "¿Puedes contarme qué necesitas?"
            )
            await save_ai_response(
                db=db,
                message_id=msg_id,
                ai_response=result["ai_response"],
                ai_model="default",
                ai_tokens_used=0,
                ai_latency_ms=0,
            )

    except Exception as e:
        logger.exception(f"❌ Error processing message from {from_number}: {e}")
        result["error"] = str(e)
        if result["message_id"]:
            await update_message_status(db, result["message_id"], "failed", str(e))

    return result
