"""
WinoWin Recepcionista — Scheduler for post-booking notifications (Fase 6)

Uses APScheduler to periodically scan for:
  1. Reminders: appointments starting in ~24h → send WhatsApp reminder
  2. Follow-ups: appointments that ended ~2h ago → send WhatsApp follow-up

Runs in-process alongside FastAPI via the lifespan startup event.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import config
from app.database import (
    get_pending_notifications,
    mark_notification_sent,
)
from app.whatsapp_client import send_message

logger = logging.getLogger("winowin.scheduler")

# ── Message templates ────────────────────────────────────────

REMINDER_TEMPLATE = (
    "¡Hola {name}! 👋 Te recordamos que mañana a las {time} tienes tu {service}. "
    "¡Te esperamos! 💇‍♀️✨"
)

FOLLOWUP_TEMPLATE = (
    "¡Hola {name}! 😊 Esperamos que te haya gustado tu {service}. "
    "¿Nos dejas una reseña? ⭐\n"
    "https://g.page/r/example/review"
)


def _build_reminder_message(client_name: str, start_time: str, service_name: str) -> str:
    """Build the reminder WhatsApp message."""
    name = client_name.strip() or "cliente"
    return REMINDER_TEMPLATE.format(
        name=name,
        time=start_time,
        service=service_name.lower(),
    )


def _build_followup_message(client_name: str, service_name: str) -> str:
    """Build the follow-up WhatsApp message."""
    name = client_name.strip() or "cliente"
    return FOLLOWUP_TEMPLATE.format(
        name=name,
        service=service_name.lower(),
    )


# ── Core notification processing ─────────────────────────────

async def _process_pending_notifications(db) -> int:
    """
    Scan for and process all pending notifications that are due.

    Returns the number of notifications sent.
    """
    notifications = await get_pending_notifications(db)

    if not notifications:
        return 0

    sent_count = 0
    for notif in notifications:
        client_name = notif.get("client_name", "cliente")
        client_phone = notif.get("client_phone", "")
        service_name = notif.get("service_name", "servicio")
        start_time = notif.get("start_time", "")
        notif_type = notif.get("type", "")

        # Build the appropriate message
        if notif_type == "reminder":
            message = _build_reminder_message(client_name, start_time, service_name)
        elif notif_type == "followup":
            message = _build_followup_message(client_name, service_name)
        else:
            logger.warning(f"⚠️ Unknown notification type '{notif_type}', skipping")
            continue

        # Send via WhatsApp
        try:
            send_result = await send_message(client_phone, message)
        except Exception as e:
            logger.error(f"❌ Exception sending notification #{notif['id']}: {e}")
            await mark_notification_sent(
                db, notif["id"], wa_message_id="", success=False
            )
            continue

        wa_msg_id = ""
        if send_result.get("success"):
            wa_msg_id = send_result.get("response", {}).get("messages", [{}])[0].get("id", "")
            sent_count += 1
            logger.info(
                f"✅ {notif_type} sent to {client_phone} "
                f"(appointment #{notif['appointment_id']}, notif #{notif['id']})"
            )
        else:
            logger.warning(
                f"⚠️ Failed to send {notif_type} to {client_phone}: "
                f"{send_result.get('error', 'unknown')[:100]}"
            )

        await mark_notification_sent(
            db, notif["id"], wa_message_id=wa_msg_id, success=send_result.get("success", False)
        )

    return sent_count


# ── Scheduled job (runs every 30 minutes) ────────────────────

async def scan_and_send_notifications():
    """
    Periodic job: scan for pending notifications and send them.

    Called by APScheduler every INTERVAL_MINUTES minutes.
    """
    from app.database import init_db  # Import here to avoid circular

    logger.info("🔍 [Scheduler] Scanning for pending notifications...")

    try:
        # Create a fresh DB connection for the scheduler job
        db = await init_db()

        sent = await _process_pending_notifications(db)

        if sent > 0:
            logger.info(f"🔔 [Scheduler] ✅ Sent {sent} notifications")
        else:
            logger.debug("🔍 [Scheduler] No pending notifications found")

        await db.close()
    except Exception as e:
        logger.exception(f"❌ [Scheduler] Error scanning notifications: {e}")


# ── Scheduler lifecycle ──────────────────────────────────────

# Singleton scheduler instance
_scheduler: AsyncIOScheduler | None = None

# How often to scan for pending notifications (in minutes)
SCAN_INTERVAL_MINUTES = 30


def start_scheduler():
    """Start the APScheduler background scheduler.

    Called from FastAPI lifespan startup event.
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("⚠️ Scheduler already running, skipping start")
        return

    _scheduler = AsyncIOScheduler()

    # Add the periodic scanning job
    _scheduler.add_job(
        scan_and_send_notifications,
        trigger=IntervalTrigger(minutes=SCAN_INTERVAL_MINUTES),
        id="scan_pending_notifications",
        name="Scan and send pending WhatsApp notifications",
        replace_existing=True,
        # Run immediately on startup so we don't wait 30 min for the first scan
        next_run_time=datetime.now(timezone.utc),
    )

    _scheduler.start()
    logger.info(
        f"⏰ Scheduler started — scanning for pending notifications "
        f"every {SCAN_INTERVAL_MINUTES} minutes"
    )


def stop_scheduler():
    """Stop the APScheduler gracefully.

    Called from FastAPI lifespan shutdown event.
    """
    global _scheduler

    if _scheduler is None:
        return

    try:
        _scheduler.shutdown(wait=False)
        logger.info("⏰ Scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping scheduler: {e}")
    finally:
        _scheduler = None
