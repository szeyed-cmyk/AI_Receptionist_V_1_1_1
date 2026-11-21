"""Ownership (tenant) scoping for every admin record lookup.

Every business-owned row has a ``business_id``. The signed admin session
stores the business the administrator owns (``request.session["business_id"]``,
written only by ``app.security.set_admin_session`` after a successful login,
setup or demo login). Admin routes never load a record by primary key alone:

    appt = get_owned_or_404(db, Appointment, appt_id, request)

which runs ``SELECT ... WHERE id = :id AND business_id = :current_business``
and answers 404 when the row does not exist **or belongs to another
business** (no existence leak). Lists, searches and counts use
``owned_query`` / ``owned_filter`` with the same condition.

Messages have no business column of their own; they are owned through their
conversation (``owned_messages_query`` joins on Conversation.business_id).
"""
from __future__ import annotations

from typing import TypeVar

from fastapi import HTTPException, Request
from sqlalchemy.orm import Query, Session

from app.database import DEFAULT_BUSINESS_ID

T = TypeVar("T")

SESSION_BUSINESS_KEY = "business_id"


def session_business_id(request: Request) -> int | None:
    """Business id stored in the signed session, or None if absent/invalid."""
    value = request.session.get(SESSION_BUSINESS_KEY)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def current_business_id(request: Request) -> int:
    """Business owned by the logged-in admin. Redirects to login if unknown."""
    business_id = session_business_id(request)
    if business_id is None:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    return business_id


def public_business_id(db: Session | None = None) -> int:
    """Business that owns rows created by the public chat/booking flow.

    A FrontDesk AI installation serves one business, so public visitors always
    book into the installation's default business.
    """
    return DEFAULT_BUSINESS_ID


def owned_filter(model, business_id: int):
    """SQL condition restricting ``model`` to rows owned by ``business_id``."""
    return model.business_id == business_id


def owned_query(db: Session, model: type[T], request: Request) -> Query:
    """``db.query(model)`` limited to the current admin's business."""
    return db.query(model).filter(owned_filter(model, current_business_id(request)))


def get_owned_or_404(db: Session, model: type[T], obj_id: int, request: Request, detail: str = "Not found") -> T:
    """Load ``model`` by id **and** owner; 404 if missing or owned by another business."""
    obj = owned_query(db, model, request).filter(model.id == obj_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def owned_messages_query(db: Session, request: Request) -> Query:
    """Messages whose conversation belongs to the current admin's business."""
    from app.models import Conversation, Message

    return (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(owned_filter(Conversation, current_business_id(request)))
    )


def admin_business_id(db: Session) -> int:
    """Business owned by the installation's administrator account.

    Stored in the ``admin_business_id`` setting (defaults to the installation's
    default business) and written into the session at login.
    """
    from app.ai_service import get_setting

    raw = (get_setting(db, "admin_business_id", "") or "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_BUSINESS_ID
