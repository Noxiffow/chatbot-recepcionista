"""
WinoWin Recepcionista — Conversation State Machine (Fase 7)

State transitions:
    IDLE → ASKING_PRICE → BOOKING → AWAITING_CONFIRMATION → CONFIRMED → COMPLETED
    Any state → COMPLAINT, HANDOFF
"""

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class ConversationState(StrEnum):
    """All possible conversation states."""
    IDLE = "IDLE"
    ASKING_PRICE = "ASKING_PRICE"           # User asked about service prices
    BOOKING = "BOOKING"                     # User wants to book, bot checking availability
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"  # Bot offered slots, awaiting user confirmation
    CONFIRMED = "CONFIRMED"                 # User confirmed booking
    COMPLETED = "COMPLETED"                 # Booking done, conversation wrapping up
    COMPLAINT = "COMPLAINT"                 # User is complaining
    HANDOFF = "HANDOFF"                     # Transferring to human


# ── State machine transition rules ────────────────────────────
# Maps (current_state, intent_detected) → new_state

TRANSITIONS = {
    # From IDLE
    (ConversationState.IDLE, "service_query"): ConversationState.ASKING_PRICE,
    (ConversationState.IDLE, "booking"): ConversationState.BOOKING,
    (ConversationState.IDLE, "complaint"): ConversationState.COMPLAINT,
    (ConversationState.IDLE, "handoff_request"): ConversationState.HANDOFF,
    (ConversationState.IDLE, "greeting"): ConversationState.IDLE,

    # From ASKING_PRICE
    (ConversationState.ASKING_PRICE, "booking"): ConversationState.BOOKING,
    (ConversationState.ASKING_PRICE, "service_query"): ConversationState.ASKING_PRICE,
    (ConversationState.ASKING_PRICE, "complaint"): ConversationState.COMPLAINT,
    (ConversationState.ASKING_PRICE, "handoff_request"): ConversationState.HANDOFF,

    # From BOOKING
    (ConversationState.BOOKING, "booking"): ConversationState.BOOKING,
    (ConversationState.BOOKING, "service_query"): ConversationState.BOOKING,
    (ConversationState.BOOKING, "complaint"): ConversationState.COMPLAINT,
    (ConversationState.BOOKING, "handoff_request"): ConversationState.HANDOFF,

    # From AWAITING_CONFIRMATION
    (ConversationState.AWAITING_CONFIRMATION, "confirm_booking"): ConversationState.CONFIRMED,
    (ConversationState.AWAITING_CONFIRMATION, "booking"): ConversationState.AWAITING_CONFIRMATION,
    (ConversationState.AWAITING_CONFIRMATION, "service_query"): ConversationState.AWAITING_CONFIRMATION,
    (ConversationState.AWAITING_CONFIRMATION, "complaint"): ConversationState.COMPLAINT,
    (ConversationState.AWAITING_CONFIRMATION, "handoff_request"): ConversationState.HANDOFF,

    # From CONFIRMED
    (ConversationState.CONFIRMED, "name_provided"): ConversationState.CONFIRMED,
    (ConversationState.CONFIRMED, "complaint"): ConversationState.COMPLAINT,
    (ConversationState.CONFIRMED, "handoff_request"): ConversationState.HANDOFF,

    # Terminal states — no transitions out
    # COMPLETED, COMPLAINT, HANDOFF are terminal
}


# ── Shared keyword lists (also used by webhook_handler) ──────

SERVICE_KEYWORDS = [
    "precio", "cuesta", "vale", "coste", "cuánto", "cuanto",
    "precios", "tarifa", "tarifas", "presupuesto",
    "alisado", "brasileño", "queratina", "hialurónico", "hialuronico",
    "taninoplastia", "liso absoluto", "orgánico", "organico",
    "células madre", "celulas madre", "catalogo", "catálogo",
    "servicio", "servicios", "tratamiento", "tratamientos",
    "corto", "mediano", "largo", "extra largo", "flequillo",
    "masculino", "ofrece", "ofrecen", "teneis", "tienes", "disponible",
]

BOOKING_KEYWORDS = [
    "reservar", "reserva", "reservame", "resérvame",
    "cita", "citas", "agendar", "agéndame", "agendame",
    "hueco", "huecos", "pedir hora", "pido hora",
    "quiero hora", "dame hora", "concretar",
    "apuntame", "apúntame", "quiero pedir",
    "confirmar cita", "confirmame", "confírmame",
]


def _is_service_query(text: str) -> str | None:
    """Check if a message is asking about services/prices. Returns a search query or None."""
    text_lower = text.lower()
    for kw in SERVICE_KEYWORDS:
        if kw in text_lower:
            skip_words = (
                "cuanto", "cuánto", "cuesta", "vale", "precio", "precios",
                "tarifa", "tarifas", "coste", "tienes", "teneis",
                "ofrece", "ofrecen", "catalogo", "catálogo",
                "servicio", "servicios", "tratamiento", "tratamientos",
                "disponible", "presupuesto",
                "quiero", "reservar", "reserva", "cita", "citas",
                "agendar", "para", "hueco", "mañana", "pasado",
            )
            words = [w for w in text_lower.split() if len(w) > 3 and w not in skip_words]
            if words:
                return " ".join(words[:5])
            return text_lower
    return None


def _is_booking_intent(text: str) -> bool:
    """Check if a message contains booking/reservation intent."""
    text_lower = text.lower()
    for kw in BOOKING_KEYWORDS:
        if kw in text_lower:
            return True
    return False


# ── Intent detection for state transitions ────────────────────

# Keywords for handoff requests
HANDOFF_KEYWORDS = [
    "hablar con una persona", "hablar con un humano", "persona real",
    "ponme con un humano", "ponme con una persona",
    "quiero hablar con alguien", "atención personal",
    "esto no me lo resuelves", "no me ayudas",
    "necesito un humano", "persona de verdad",
    "agente", "supervisor", "encargado", "gerente",
    "responsable", "dueño", "dueña", "jefe", "jefa",
]

# Keywords detecting frustration
FRUSTRATION_KEYWORDS = [
    "no", "mal", "error", "equivocado", "equivocada",
    "no es eso", "no es lo que", "no entiendes",
    "otra vez", "repitiendo", "siempre igual",
    "desastre", "fatal", "pésimo", "pesimo", "horrible",
    "inútil", "inutil", "no sirves", "no funcionas",
    "no me entiendes", "no comprendes", "ya te lo he dicho",
]

# Emergency keywords — immediate handoff
EMERGENCY_KEYWORDS = [
    "emergencia", "urgencia", "urgente",
    "accidente", "quemadura", "reacción alérgica",
    "reaccion alergica", "alergia",
]


def detect_handoff(text: str) -> bool:
    """Check if the user is explicitly requesting a human handoff."""
    text_lower = text.lower()
    for kw in HANDOFF_KEYWORDS:
        if kw in text_lower:
            return True
    # Emergency?
    for kw in EMERGENCY_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def detect_frustration(text: str) -> bool:
    """Check if the user message shows frustration."""
    text_lower = text.lower()
    count = sum(1 for kw in FRUSTRATION_KEYWORDS if kw in text_lower)
    return count >= 2  # At least 2 frustration markers


def detect_intent(
    text: str,
    current_state: str,
    context: dict | None = None,
    history: list[dict] | None = None,
) -> str:
    """
    Detect the intent of the current message for state transition purposes.
    
    Returns one of:
        'greeting', 'service_query', 'booking', 'confirm_booking',
        'name_provided', 'complaint', 'handoff_request', 'unknown'
    """
    text_lower = text.lower().strip()
    
    # 1. Check for handoff first (highest priority)
    if detect_handoff(text):
        return "handoff_request"
    
    # 2. Check for frustration → complaint
    if detect_frustration(text):
        return "complaint"
    
    # 3. Check for booking confirmation
    if current_state == ConversationState.AWAITING_CONFIRMATION:
        confirm_keywords = [
            "sí", "si", "ok", "vale", "genial", "perfecto", "de acuerdo",
            "confirmo", "confirmar", "reservalo", "resérvalo", "adelante",
            "venga", "dale", "claro", "por supuesto",
        ]
        for kw in confirm_keywords:
            if text_lower == kw or text_lower.startswith(kw):
                return "confirm_booking"
        # Also check for time confirmations (e.g., "a las 10", "10:00")
        import re
        if re.match(r'^(a las?\s+)?\d{1,2}[:h]\d{2}', text_lower):
            return "confirm_booking"
    
    # 4. Check for name provision (in CONFIRMED state)
    if current_state == ConversationState.CONFIRMED:
        if len(text_lower.split()) <= 4 and not any(
            kw in text_lower for kw in ["precio", "cita", "reserva"]
        ):
            return "name_provided"
    
    # 5. Check for booking intent
    if _is_booking_intent(text):
        return "booking"
    
    # 6. Check for service query
    if _is_service_query(text):
        return "service_query"
    
    # 7. Check for greeting
    greeting_keywords = [
        "hola", "buenas", "buenos días", "buenos dias",
        "buenas tardes", "buenas noches", "hey", "saludos",
        "qué tal", "que tal", "cómo estás", "como estas",
    ]
    for kw in greeting_keywords:
        if kw in text_lower:
            return "greeting"
    
    return "unknown"


def compute_next_state(
    current_state: str,
    intent: str,
    context: dict | None = None,
) -> str:
    """
    Compute the next state based on current state and detected intent.
    Uses the TRANSITIONS table. Defaults to staying in current state.
    """
    state = ConversationState(current_state) if current_state else ConversationState.IDLE
    
    # Check transition table
    next_state = TRANSITIONS.get((state, intent))
    if next_state:
        return next_state.value
    
    # If booking intent and not in terminal state → move to BOOKING
    if intent == "booking" and state not in (
        ConversationState.COMPLETED, ConversationState.COMPLAINT, ConversationState.HANDOFF
    ):
        return ConversationState.BOOKING.value
    
    # If service_query and in IDLE → ASKING_PRICE
    if intent == "service_query" and state == ConversationState.IDLE:
        return ConversationState.ASKING_PRICE.value
    
    # Stay in current state
    return state.value


def get_state_instructions(state: str) -> str:
    """
    Return instructions for the AI based on the current conversation state.
    These are injected into the system prompt.
    """
    instructions = {
        ConversationState.IDLE: (
            "ESTADO: El cliente acaba de iniciar conversación. "
            "Saluda cordialmente y pregunta en qué puedes ayudarle."
        ),
        ConversationState.ASKING_PRICE: (
            "ESTADO: El cliente está interesado en precios/servicios. "
            "Proporciona información precisa del catálogo. "
            "Si muestra interés en reservar, sugiérele agendar una cita."
        ),
        ConversationState.BOOKING: (
            "ESTADO: El cliente quiere reservar una cita. "
            "Usa SOLO los datos de disponibilidad real que te proporciona el sistema. "
            "NO inventes fechas ni horarios. Pregunta qué día y hora prefiere."
        ),
        ConversationState.AWAITING_CONFIRMATION: (
            "ESTADO: Has ofrecido horarios disponibles y esperas confirmación del cliente. "
            "Si el cliente confirma ('sí', 'vale', una hora concreta), pide su nombre completo. "
            "Si cambia de opinión, vuelve a consultar disponibilidad."
        ),
        ConversationState.CONFIRMED: (
            "ESTADO: El cliente ha confirmado. Pregunta su nombre completo para finalizar la reserva. "
            "Cuando tengas el nombre, confirma los detalles y dile que la cita está registrada."
        ),
        ConversationState.COMPLAINT: (
            "ESTADO: El cliente está insatisfecho. Sé especialmente empático. "
            "Discúlpate por las molestias y ofrece derivar a un compañero humano. "
            "NO intentes resolverlo todo tú — mejor deriva."
        ),
        ConversationState.HANDOFF: (
            "ESTADO: Vas a derivar al cliente a un compañero humano. "
            "Dile que le pasas con una persona, que estará con él/ella en breve. "
            "Sé amable y tranquilizador."
        ),
        ConversationState.COMPLETED: (
            "ESTADO: La reserva está completada. Despídete cordialmente y "
            "recuerda al cliente que puede contactar de nuevo si lo necesita."
        ),
    }
    return instructions.get(ConversationState(state), "")
