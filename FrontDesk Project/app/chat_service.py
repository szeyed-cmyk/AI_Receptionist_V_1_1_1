"""Chat orchestration: create/bind conversation, persist messages, call AI."""
from __future__ import annotations

import secrets
import re
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.ai_service import generate_reply
from app.models import Conversation, Message
from app.ownership import owned_filter, public_business_id


SESSION_CONV_KEY = "visitor_conversation_id"
SESSION_TOKEN_KEY = "visitor_token"


def _visitor_token(request: Request) -> str:
    token = request.session.get(SESSION_TOKEN_KEY)
    if not token:
        token = secrets.token_urlsafe(24)
        request.session[SESSION_TOKEN_KEY] = token
    return token


async def handle_chat_async(db: Session, request: Request, message: str) -> dict:
    token = _visitor_token(request)
    session_conv_id = request.session.get(SESSION_CONV_KEY)

    conv: Conversation | None = None
    if session_conv_id is not None:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == session_conv_id,
                Conversation.visitor_token == token,
                owned_filter(Conversation, public_business_id(db)),
            )
            .first()
        )

    if conv is None:
        conv = Conversation(channel="web", visitor_token=token, business_id=public_business_id(db))
        db.add(conv)
        db.commit()
        db.refresh(conv)
        request.session[SESSION_CONV_KEY] = conv.id
        if settings.demo_mode and request.session.get("demo_session"):
            from app.demo_session import demo_created
            demo_created(request, "conversation", conv.id, (message or "Web conversation")[:100])

    user_msg = Message(conversation_id=conv.id, role="user", content=message)
    db.add(user_msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    from app.config import demo_uses_live_ai
    from app.demo_ai import local_demo_reply
    from app.models import KnowledgeItem

    def _scripted_demo_reply() -> str:
        from app.ai_service import get_appointment_minutes, is_length_question, book_appointment_tool
        from app.demo_ai import booking_prompt
        minutes = get_appointment_minutes(db, conv.business_id)
        fields = re.search(r"(.+?),\s*([+0-9][0-9 ()-]{5,}),\s*(.+?),\s*(.+)", message, re.IGNORECASE)
        booking_request = bool(fields) or (
            any(word in message.lower() for word in ("book", "appointment", "reserve")) and not is_length_question(message)
        )
        if not booking_request:
            return local_demo_reply(
                message,
                db.query(KnowledgeItem).filter(owned_filter(KnowledgeItem, conv.business_id), KnowledgeItem.is_active.is_(True)).all(),
                minutes,
            )
        # Booking intent takes precedence over broad FAQ keyword matches.
        if fields:
            name, phone, service, when = [part.strip() for part in fields.groups()]
            # "I would like to book an appointment name: Ahmad" -> "Ahmad"
            labelled = re.search(r"\bname\s*[:=\-]\s*(.+)$", name, re.IGNORECASE)
            if labelled:
                name = labelled.group(1).strip()
            if len(name) < 2 or len(name) > 100 or len(service) > 150 or len(when) > 150:
                return "Please provide a valid name, service and preferred time so I can check the appointment."
            result = book_appointment_tool(db, conv.id, name, phone, service, when)
            text = result.get("message") or result.get("error") or ""
            if result.get("success"):
                _register_demo_appointment(request, result["appointment_id"], name, service)
            return text
        return booking_prompt(minutes)

    if settings.demo_mode:
        if demo_uses_live_ai():
            from app.ai_service import redact_secrets
            from app.demo_ai_limits import consume_demo_ai_turn, fallback_reply_prefix
            allowed, _reason = consume_demo_ai_turn(request, message)
            if allowed:
                reply = await generate_reply(
                    db, conv.id, message, max_tokens=settings.demo_ai_max_tokens,
                )
                reply = redact_secrets(reply, settings.ai_api_key)
                _register_latest_demo_appointment(request, db, conv.id)
            else:
                reply = fallback_reply_prefix() + " " + _scripted_demo_reply()
        else:
            # Unchanged guided demo: no network, local FAQ + booking parser.
            reply = _scripted_demo_reply()
    else:
        reply = await generate_reply(db, conv.id, message)
    assistant_msg = Message(conversation_id=conv.id, role="assistant", content=reply)
    db.add(assistant_msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"conversation_id": conv.id, "reply": reply}


def _register_demo_appointment(request: Request, appointment_id: int, name: str, service: str) -> None:
    """Let this demo session manage the appointment it just booked (no-op outside demo)."""
    if settings.demo_mode and request.session.get("demo_session"):
        from app.demo_session import demo_created
        demo_created(request, "appointment", appointment_id, f"{name} - {service}"[:100])


def _register_latest_demo_appointment(request: Request, db, conversation_id: int) -> None:
    """If live demo AI just booked via the tool, grant this session ownership of it."""
    if not (settings.demo_mode and request.session.get("demo_session")):
        return
    from app.models import Appointment
    latest = (
        db.query(Appointment)
        .filter(Appointment.conversation_id == conversation_id)
        .order_by(Appointment.id.desc())
        .first()
    )
    if latest is not None:
        _register_demo_appointment(request, latest.id, latest.customer_name or "", latest.service or "")


def reject_foreign_conversation(db: Session, request: Request, conversation_id: int | None) -> None:
    """If the client sends a conversation_id that is not theirs, raise 403.

    Used by the public route to make ownership checks explicit for auditors.
    The service itself never trusts the client id for loading history.
    """
    if conversation_id is None:
        return
    token = request.session.get(SESSION_TOKEN_KEY)
    session_conv_id = request.session.get(SESSION_CONV_KEY)
    if session_conv_id is not None and int(conversation_id) == int(session_conv_id):
        # Matches the session-owned conversation — OK (still re-verified by token).
        if token:
            owned = (
                db.query(Conversation)
                .filter(
                    Conversation.id == conversation_id,
                    Conversation.visitor_token == token,
                )
                .first()
            )
            if owned:
                return
        raise HTTPException(status_code=403, detail="Conversation does not belong to this visitor")
    # Client tried a foreign / guessed sequential id
    raise HTTPException(status_code=403, detail="Conversation does not belong to this visitor")
