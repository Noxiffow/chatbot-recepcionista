"""
WinoWin Recepcionista — Chatbot WhatsApp Business
Webhook receiver + AI integration for Meta Cloud API

Fase 2: Backend FastAPI + Webhook + SQLite logging
Fase 3: Integración IA Groq (llama-3.3-70b)
Fase 5B: Disponibilidad real + reservas

Run: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
import json
import logging
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.config import config
from app.database import (
    init_db, get_stats,
    generate_slots, get_availability, get_available_slots,
    get_available_dates, book_appointment, cancel_appointment,
    get_appointments_for_date,
)
from app.webhook_handler import parse_webhook_body, process_message
from app.whatsapp_client import check_health
from app.scheduler import start_scheduler, stop_scheduler

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("winowin.recepcionista")

# ── Global DB connection ────────────────────────────────────
db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Get the database connection."""
    global db
    if db is None:
        db = await init_db()
    return db


# ── Lifespan (modern FastAPI startup/shutdown) ──────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown handlers."""
    global db

    # Startup
    logger.info("=" * 60)
    logger.info("🚀 WinoWin Recepcionista starting up...")
    logger.info(f"   Business: {config.business_name} ({config.business_type})")
    logger.info(f"   WhatsApp PHONE_NUMBER_ID: {config.phone_number_id}")
    logger.info(f"   WhatsApp Token: {'✅ SET' if config.whatsapp_token else '❌ NOT SET'}")
    logger.info(f"   Groq AI: {'✅ ENABLED' if config.groq_enabled else '⚠️ NOT CONFIGURED'}")
    logger.info(f"   Can send messages: {'❌ BLOCKED (payment required)' if config.can_send_messages else '❌ NO TOKEN'}")
    logger.info(f"   Database: {config.database_path}")
    logger.info("=" * 60)

    # Init database
    db = await init_db()

    # Fase 5B: Generate availability slots
    try:
        slots_created = await generate_slots(db, days=30)
        logger.info(f"📅 Availability slots: {slots_created} new slots generated (30 days)")
    except Exception as e:
        logger.error(f"❌ Failed to generate slots: {e}")

    # Check WhatsApp health
    health = await check_health()
    waba_health = health.get("health_status", {})
    can_send = waba_health.get("can_send_message", "unknown")
    logger.info(f"🏥 WABA Health: can_send_message={can_send}")

    # Fase 6: Start APScheduler for reminders & follow-ups
    try:
        start_scheduler()
        logger.info("⏰ Scheduler started for reminders & follow-ups")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")

    yield  # App runs here

    # Shutdown
    logger.info("👋 WinoWin Recepcionista shutting down...")

    # Fase 6: Stop scheduler
    try:
        stop_scheduler()
    except Exception as e:
        logger.error(f"❌ Error stopping scheduler: {e}")
    if db:
        await db.close()
        logger.info("   Database connection closed.")


# ── FastAPI App ─────────────────────────────────────────────
app = FastAPI(
    title="WinoWin Recepcionista",
    description="Chatbot WhatsApp Business con IA (Groq + Llama 3) · Fase 6",
    version="0.4.0",
    lifespan=lifespan,
)


# ── Root / Health check ─────────────────────────────────────
@app.get("/")
async def root():
    """Health check endpoint."""
    stats = {}
    if db:
        try:
            stats = await get_stats(db)
        except Exception as e:
            stats = {"error": str(e)}

    health = await check_health()

    return {
        "app": "WinoWin Recepcionista",
        "version": "0.3.0",
        "status": "ok",
        "groq_enabled": config.groq_enabled,
        "waba_health": health.get("health_status", {}),
        "database": stats,
    }


@app.get("/health")
async def health_detail():
    """Detailed health check."""
    return await root()


@app.get("/health/meta")
async def health_meta():
    """Meta-specific health check."""
    return await check_health()


# ── Webhook verification (Meta GET) ─────────────────────────
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    """Meta calls this endpoint to verify the webhook URL."""
    logger.info(f"🔐 Webhook verification: mode={hub_mode}, token={'***' if hub_verify_token else 'EMPTY'}")

    if hub_mode == "subscribe" and hub_verify_token == config.verify_token:
        logger.info("✅ Webhook verified successfully by Meta")
        return PlainTextResponse(hub_challenge)

    logger.warning(f"❌ Webhook verification FAILED — wrong token")
    return Response(status_code=403)


# ── Webhook receiver (Meta POST) ────────────────────────────
@app.post("/webhook")
async def receive_whatsapp(request: Request):
    """
    Receive incoming WhatsApp messages via Meta Cloud API webhook.

    Processing pipeline:
    1. Parse webhook body → extract messages
    2. Save each message to SQLite
    3. Update conversation tracking
    4. Check for booking intent → query real availability (Fase 5B)
    5. Generate AI response via Groq (if configured)
    6. Save AI response to DB
    7. (Send response back when Meta unblocks)
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        logger.warning("📩 Received non-JSON webhook body")
        return Response(status_code=400)

    logger.info(f"📩 Webhook POST received — {len(json.dumps(body))} bytes")

    # Parse messages
    messages = parse_webhook_body(body)

    if not messages:
        logger.debug("📩 Webhook received but no messages found (status update?)")
        # Still return 200 — Meta requires this
        return Response(status_code=200)

    # Process each message
    db_conn = await get_db()
    results = []

    for msg in messages:
        result = await process_message(
            db=db_conn,
            parsed_msg=msg,
            try_send=True,  # ✅ Payment method added — WABA is AVAILABLE
        )
        results.append(result)

    # Log summary
    processed = [r for r in results if r["message_id"]]
    errors = [r for r in results if r.get("error")]
    logger.info(
        f"✅ Processed {len(processed)} messages, "
        f"{len(errors)} errors"
    )

    return Response(status_code=200)


# ── Dashboard (simple HTML) ─────────────────────────────────
@app.get("/dashboard")
async def dashboard():
    """Simple web dashboard showing recent messages."""
    db_conn = await get_db()

    # Get recent messages
    cursor = await db_conn.execute(
        """
        SELECT wa_message_id, from_number, text, ai_response, media_type,
               direction, status, received_at
        FROM messages
        ORDER BY received_at DESC
        LIMIT 50
        """
    )
    rows = await cursor.fetchall()

    stats = await get_stats(db_conn)

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WinoWin Recepcionista — Dashboard</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; }}
            .header {{ background: #075e54; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .header h1 {{ font-size: 24px; }}
            .stats {{ display: flex; gap: 15px; margin-bottom: 20px; }}
            .stat {{ background: white; padding: 15px 25px; border-radius: 10px; flex: 1; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .stat .number {{ font-size: 32px; font-weight: bold; color: #075e54; }}
            .stat .label {{ font-size: 12px; color: #666; margin-top: 5px; }}
            .messages {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .message {{ border-bottom: 1px solid #eee; padding: 12px 0; }}
            .message:last-child {{ border-bottom: none; }}
            .msg-meta {{ font-size: 11px; color: #999; margin-bottom: 4px; }}
            .msg-from {{ color: #075e54; font-weight: 600; }}
            .msg-text {{ margin: 4px 0; }}
            .msg-ai {{ background: #dcf8c6; padding: 8px 12px; border-radius: 8px; margin-top: 6px; }}
            .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; }}
            .badge-in {{ background: #e3f2fd; color: #1565c0; }}
            .badge-out {{ background: #e8f5e9; color: #2e7d32; }}
            .badge-processed {{ background: #c8e6c9; color: #1b5e20; }}
            .badge-failed {{ background: #ffcdd2; color: #b71c1c; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 WinoWin Recepcionista</h1>
            <p style="opacity:0.8; margin-top:5px;">Chatbot WhatsApp Business · {config.business_name} ({config.business_type})</p>
        </div>

        <div class="stats">
            <div class="stat">
                <div class="number">{stats['total_messages']}</div>
                <div class="label">Mensajes totales</div>
            </div>
            <div class="stat">
                <div class="number">{stats['active_conversations']}</div>
                <div class="label">Conversaciones activas</div>
            </div>
            <div class="stat">
                <div class="number">{stats['processed_messages']}</div>
                <div class="label">Procesados por IA</div>
            </div>
            <div class="stat">
                <div class="number">{'🟢' if config.groq_enabled else '🔴'}</div>
                <div class="label">IA Groq</div>
            </div>
        </div>

        <div class="messages">
            <h2 style="margin-bottom:15px;">📨 Últimos mensajes</h2>
    """

    for row in rows:
        direction = row["direction"]
        status = row["status"]
        badge_class = "badge-in" if direction == "incoming" else "badge-out"
        status_class = "badge-processed" if status in ("processed", "responded") else ("badge-failed" if status == "failed" else "")

        html += f"""
            <div class="message">
                <div class="msg-meta">
                    <span class="badge {badge_class}">{direction}</span>
                    <span class="badge {status_class}">{status}</span>
                    <span class="msg-from">{row['from_number']}</span>
                    · {row['received_at']}
                    <span style="color:#999;"> · {row['media_type']}</span>
                </div>
                <div class="msg-text">{row['text'] or '<em>(sin texto)</em>'}</div>
        """

        if row["ai_response"]:
            html += f'<div class="msg-ai">🤖 {row["ai_response"]}</div>'

        html += "</div>"

    html += """
            </div>
        </body>
        </html>
    """

    return HTMLResponse(content=html)


# ── API: recent messages ────────────────────────────────────
@app.get("/api/messages")
async def api_messages(limit: int = 20):
    """Get recent messages as JSON."""
    db_conn = await get_db()
    cursor = await db_conn.execute(
        """
        SELECT id, wa_message_id, from_number, text, ai_response,
               media_type, direction, status, received_at
        FROM messages
        ORDER BY received_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = await cursor.fetchall()
    return {"messages": [dict(row) for row in rows], "count": len(rows)}


# ── API: stats ──────────────────────────────────────────────
@app.get("/api/stats")
async def api_stats():
    """Get stats as JSON."""
    db_conn = await get_db()
    stats = await get_stats(db_conn)
    health = await check_health()
    return {
        **stats,
        "groq_enabled": config.groq_enabled,
        "waba_health": health.get("health_status", {}),
        "business_name": config.business_name,
        "business_type": config.business_type,
    }


# ── API: services catalog ───────────────────────────────────
@app.get("/api/services")
async def api_services(query: str = "", category: str = ""):
    """Search the services catalog."""
    from app.database import search_services, get_services_by_category, get_all_categories

    db_conn = await get_db()

    if category:
        services = await get_services_by_category(db_conn, category)
    elif query:
        services = await search_services(db_conn, query)
    else:
        services = await search_services(db_conn, "")

    categories = await get_all_categories(db_conn)

    return {
        "services": services,
        "count": len(services),
        "categories": categories,
    }


# ── API: test chat (simulated, no webhook needed) ────────────
@app.get("/api/test-chat")
async def test_chat(msg: str = "¿Cuánto cuesta un alisado brasileño corto?"):
    """
    Simulate a chat message through the full pipeline.
    Returns the AI response and any catalog matches found.
    """
    from app.database import search_services, get_all_categories
    from app.webhook_handler import _is_service_query
    from app.groq_client import generate_response

    db_conn = await get_db()

    # Step 1: Check if it's a service query
    search_query = _is_service_query(msg)
    catalog_services = None
    if search_query:
        catalog_services = await search_services(db_conn, search_query)
        if not catalog_services:
            catalog_services = await search_services(db_conn, "")

    # Step 2: Generate AI response with catalog
    ai_result = await generate_response(
        user_message=msg,
        conversation_history=None,
        catalog_services=catalog_services,
    )

    return {
        "message": msg,
        "is_service_query": search_query is not None,
        "search_query": search_query,
        "catalog_matches": len(catalog_services) if catalog_services else 0,
        "catalog_services": catalog_services[:5] if catalog_services else [],
        "ai_response": ai_result.get("response"),
        "ai_model": ai_result.get("model"),
        "ai_latency_ms": ai_result.get("latency_ms"),
        "ai_tokens": ai_result.get("tokens_used"),
        "error": ai_result.get("error"),
    }


# ── API: Availability (Fase 5B) ─────────────────────────────
@app.get("/api/availability")
async def api_availability(date_str: str = "", duration_min: int = 120):
    """Check real availability for a date and duration."""
    from datetime import date as dt_date

    db_conn = await get_db()

    if not date_str:
        date_str = dt_date.today().isoformat()

    slots = await get_available_slots(db_conn, date_str, duration_min)
    all_slots = await get_availability(db_conn, date_str)

    return {
        "date": date_str,
        "duration_min": duration_min,
        "available_slots": slots,
        "available_count": len(slots),
        "all_slots_count": len(all_slots),
        "free_slots_count": sum(1 for s in all_slots if s["status"] == "free"),
        "booked_slots_count": sum(1 for s in all_slots if s["status"] == "booked"),
    }


@app.get("/api/availability/dates")
async def api_available_dates(duration_min: int = 120, limit: int = 7):
    """Get upcoming dates with availability for a given duration."""
    db_conn = await get_db()
    dates = await get_available_dates(db_conn, duration_min, limit)
    return {
        "duration_min": duration_min,
        "available_dates": dates,
        "count": len(dates),
    }


# ── API: Appointments (Fase 5B) ─────────────────────────────
@app.get("/api/appointments")
async def api_appointments(date_str: str = ""):
    """List appointments for a date."""
    from datetime import date as dt_date

    db_conn = await get_db()
    if not date_str:
        date_str = dt_date.today().isoformat()

    appointments = await get_appointments_for_date(db_conn, date_str)
    return {
        "date": date_str,
        "appointments": appointments,
        "count": len(appointments),
    }


@app.post("/api/appointments/book")
async def api_book_appointment(
    service_id: int = 1,
    client_name: str = "Test Client",
    client_phone: str = "34123456789",
    date_str: str = "",
    start_time: str = "10:00",
):
    """Book an appointment (test endpoint)."""
    from datetime import date as dt_date

    db_conn = await get_db()
    if not date_str:
        date_str = dt_date.today().isoformat()

    appointment = await book_appointment(
        db_conn, service_id, client_name, client_phone, date_str, start_time
    )

    if appointment:
        return {"success": True, "appointment": appointment}
    else:
        return {"success": False, "error": "Slots not available"}


@app.post("/api/appointments/cancel")
async def api_cancel_appointment(appointment_id: int):
    """Cancel an appointment."""
    db_conn = await get_db()
    ok = await cancel_appointment(db_conn, appointment_id)
    return {"success": ok, "appointment_id": appointment_id}


@app.post("/api/slots/generate")
async def api_generate_slots(days: int = 30):
    """Generate schedule slots (idempotent)."""
    db_conn = await get_db()
    count = await generate_slots(db_conn, days)
    return {"success": True, "slots_created": count, "days": days}
