"""
Notification service responsible for:
- Persisting notification records
- Dispatching outbound messages (email, WhatsApp, SMS) via pluggable channels
- AI-generated alerts via Groq (Phase 5)
"""

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import orm
from app.services.ai import draft_logistics_alert
from app.utils.retry import with_retries

logger = logging.getLogger(__name__)


async def _send_email(recipient_email: str, subject: str, body: str) -> None:
    """
    Send an email using Postmark.

    This uses the Postmark server token configured in environment variables.
    """
    if not (settings.postmark_server_token and settings.email_from):
        # In production, log that email could not be sent due to missing config
        return

    from app.observability.langfuse import create_trace

    trace = create_trace(
        name="email_notification_sent",
        metadata={"subject": subject},
        tags=["notification", "email"],
    )
    span = None
    if trace is not None:
        try:
            span = trace.start_observation(
                name="postmark_send_email",
                as_type="span",
                input={"recipient": recipient_email, "subject": subject},
            )
        except Exception:
            pass

    payload = {
        "From": settings.email_from,
        "To": recipient_email,
        "Subject": subject,
        "TextBody": body,
    }

    async def _post() -> httpx.Response:
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.post(
                "https://api.postmarkapp.com/email",
                headers={
                    "X-Postmark-Server-Token": settings.postmark_server_token,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

    resp = await with_retries(_post)
    success = resp is not None and resp.is_success
    if not success:
        logger.warning("postmark send_email failed or retries exhausted")
    if span is not None:
        try:
            if success:
                span.update(output={"status": "sent"})
            else:
                span.update(output={"status": "failed"}, level="ERROR", status_message="postmark send failed")
            span.end()
        except Exception:
            pass


async def _send_whatsapp(phone_number: str, message: str) -> None:
    """
    Send a text message via the WhatsApp proxy server.

    Posts to the proxy using the same payload format it expects, authenticated
    with WHATSAPP_WEBHOOK_SECRET.  Falls back to Meta's API directly if the
    proxy URL is not configured.
    """
    # --- Proxy path (preferred) -------------------------------------------
    if settings.whatsapp_proxy_url and settings.whatsapp_webhook_secret:
        from app.observability.langfuse import create_trace

        trace = create_trace(
            name="whatsapp_notification_sent",
            metadata={"phone_suffix": phone_number[-4:] if len(phone_number) >= 4 else "****"},
            tags=["notification", "whatsapp"],
        )
        span = None
        if trace is not None:
            try:
                span = trace.start_observation(
                    name="whatsapp_send_message",
                    as_type="span",
                    input={"phone_suffix": phone_number[-4:] if len(phone_number) >= 4 else "****"},
                )
            except Exception:
                pass

        payload: dict[str, Any] = {
            "to": phone_number.lstrip("+"),
            "message": {
                "type": "text",
                "content": message[:4096],
            },
        }

        async def _post_proxy() -> httpx.Response:
            async with httpx.AsyncClient(timeout=10.0) as client:
                return await client.post(
                    settings.whatsapp_proxy_url,
                    headers={
                        "X-Webhook-Secret": settings.whatsapp_webhook_secret,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

        resp = await with_retries(_post_proxy)
        success = resp is not None and resp.is_success
        if not success:
            logger.warning("whatsapp proxy send failed or retries exhausted")
        if span is not None:
            try:
                if success:
                    span.update(output={"status": "sent"})
                else:
                    span.update(output={"status": "failed"}, level="ERROR", status_message="whatsapp proxy send failed")
                span.end()
            except Exception:
                pass
        return

    # --- Direct Meta API fallback -----------------------------------------
    _placeholder = ("your-", "your_")
    if not (settings.whatsapp_access_token and settings.whatsapp_phone_number_id):
        return
    if any(settings.whatsapp_access_token.startswith(p) for p in _placeholder):
        return

    from app.observability.langfuse import create_trace

    trace = create_trace(
        name="whatsapp_notification_sent",
        metadata={"phone_suffix": phone_number[-4:] if len(phone_number) >= 4 else "****"},
        tags=["notification", "whatsapp"],
    )
    span = None
    if trace is not None:
        try:
            span = trace.start_observation(
                name="whatsapp_send_message",
                as_type="span",
                input={"phone_suffix": phone_number[-4:] if len(phone_number) >= 4 else "****"},
            )
        except Exception:
            pass

    url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/messages"
    meta_payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": phone_number.lstrip("+"),
        "type": "text",
        "text": {"body": message[:4096]},
    }

    async def _post() -> httpx.Response:
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_access_token}",
                    "Content-Type": "application/json",
                },
                json=meta_payload,
            )

    resp = await with_retries(_post)
    success = resp is not None and resp.is_success
    if not success:
        logger.warning("whatsapp send failed or retries exhausted")
    if span is not None:
        try:
            if success:
                span.update(output={"status": "sent"})
            else:
                span.update(output={"status": "failed"}, level="ERROR", status_message="whatsapp send failed")
            span.end()
        except Exception:
            pass


async def _send_sms(phone_number: str, message: str) -> None:
    """
    Placeholder SMS sender. Replace with Twilio or other SMS provider.
    Set SMS_API_KEY and implement the provider call below to enable.
    """
    if not settings.sms_api_key or settings.sms_api_key.startswith("your-"):
        return

    # TODO: implement SMS provider (e.g. Twilio) — currently a no-op stub.
    logger.info("SMS skipped for %s — provider not yet implemented.", phone_number[-4:])


async def send_shipment_update_notification(
    session: AsyncSession,
    shipment: orm.Shipment,
    old_status: str,
    new_status: str,
) -> None:
    """
    High-level notification used when shipment status changes.
    Persists Notification record and dispatches via available channels.
    """
    from app.observability.langfuse import create_trace

    create_trace(
        name="container_status_updated",
        metadata={
            "container_number": shipment.container_number,
            "old_status": old_status,
            "new_status": new_status,
        },
        tags=["shipment", "status_change"],
    )

    user = shipment.user

    message = (
        f"Container {shipment.container_number} status changed from "
        f"{old_status} to {new_status}."
    )

    # Example of additional intelligence for demurrage risk messaging.
    if new_status.lower() == "arrived at port":
        message += (
            " Recommended action: Begin customs clearance to avoid demurrage fees."
        )

    notification = orm.Notification(
        shipment_id=shipment.id,
        message=message,
    )
    session.add(notification)
    await session.commit()

    # Dispatch through available channels.
    if user.email:
        await _send_email(
            recipient_email=user.email,
            subject=f"Shipment update: {shipment.container_number}",
            body=message,
        )

    if user.phone:
        # Future: differentiate between WhatsApp and SMS per user preferences.
        await _send_whatsapp(phone_number=user.phone, message=message)
        await _send_sms(phone_number=user.phone, message=message)


def _build_alert_context(shipment: orm.Shipment, new_status: str) -> dict[str, Any]:
    """Build context dict for AI alert generator."""
    return {
        "container_number": shipment.container_number,
        "status": new_status,
        "location": getattr(shipment, "location", None) or getattr(shipment, "carrier", None),
        "eta": shipment.eta.isoformat() if shipment.eta else None,
        "free_days_remaining": getattr(shipment, "free_days_remaining", None),
        "risk_level": getattr(shipment, "demurrage_risk", None),
    }


async def send_shipment_status_change_notification(
    session: AsyncSession,
    shipment: orm.Shipment,
    old_status: str,
    new_status: str,
) -> None:
    """
    Status-change-driven alerts. Uses Groq for AI-generated message when configured;
    otherwise falls back to template. Persists to notifications and optionally
    to ai_generated_messages; sends via email and WhatsApp.
    """
    from app.observability.langfuse import create_trace

    create_trace(
        name="notification_sent",
        metadata={
            "container_number": shipment.container_number,
            "old_status": old_status,
            "new_status": new_status,
        },
        tags=["shipment", "notification"],
    )

    user = shipment.user

    # Fallback template
    message_lines = [
        f"Container {shipment.container_number} has changed status.",
        f"Previous status: {old_status}",
        f"New status: {new_status}",
    ]
    if new_status.lower() == "arrived at port":
        message_lines.append("Free days countdown has started.")
        message_lines.append("Recommended action: Begin customs clearance.")
    fallback_body = "\n".join(message_lines)

    # AI-generated body when Groq is configured
    context = _build_alert_context(shipment, new_status)
    ai_body = await draft_logistics_alert(context)
    body = ai_body if ai_body else fallback_body

    notification = orm.Notification(
        shipment_id=shipment.id,
        message=body,
    )
    session.add(notification)
    await session.commit()

    if ai_body:
        session.add(
            orm.AIGeneratedMessage(
                shipment_id=shipment.id,
                channel="multi",
                message=body,
            )
        )
        await session.commit()

    subject = "Shipment Update"
    if user.email:
        await _send_email(recipient_email=user.email, subject=subject, body=body)
    if user.phone:
        await _send_whatsapp(phone_number=user.phone, message=body)
        await _send_sms(phone_number=user.phone, message=body)
