"""Shared web helpers: one template-context builder, pagination, search terms."""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.config import settings
from app.demo_session import demo_blocks_mutation, demo_writes, is_demo_session
from app.security import csrf_token as make_csrf
from app.templating import templates

SEARCH_MAX_LENGTH = 100
LIKE_ESCAPE = "\\"


def can_mutate(request: Request, kind: str, item_id: int) -> bool:
    """Template helper: may this session edit/delete the given row?"""
    return not demo_blocks_mutation(request, kind, item_id)


def render(request: Request, name: str, context: dict | None = None):
    """Single shared TemplateResponse builder for auth and admin routes."""
    ctx = {
        "request": request,
        "csrf_token": make_csrf(request),
        "demo_mode": settings.demo_mode,
        "demo_allow_ai": bool(settings.demo_mode and settings.demo_allow_ai),
        "demo_session": is_demo_session(request),
        "upcoming_count": 0,
        "business_name": "FrontDesk AI",
        "demo_writes": demo_writes(request),
        # True in production; in demo only for rows this session created.
        # (v1.0.8 hid Edit/Delete buttons in production by mistake.)
        "demo_can_mutate": can_mutate,
    }
    if context:
        ctx.update(context)
    return templates.TemplateResponse(request, name, ctx)


def clean_query(q: str) -> str:
    return (q or "").strip()[:SEARCH_MAX_LENGTH]


def like_term(q: str) -> str:
    """Build a LIKE pattern with %, _ and the escape char escaped.

    The returned string is only ever passed to SQLAlchemy ``ilike(...,
    escape=LIKE_ESCAPE)`` so it is sent as a bound parameter, never
    interpolated into SQL text.
    """
    value = clean_query(q)
    value = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{value}%"


def page_params(request: Request) -> tuple[int, int]:
    try:
        page = max(1, min(100000, int(request.query_params.get("page", "1"))))
    except ValueError:
        page = 1
    return page, (page - 1) * settings.page_size


def pagination(request: Request, total: int) -> dict:
    page, _ = page_params(request)
    pages = max(1, (total + settings.page_size - 1) // settings.page_size)
    return {"page": min(page, pages), "pages": pages, "total": total}


def business_context(db: Session, request: Request | None = None) -> dict:
    """Shared header context; the upcoming badge counts only owned appointments."""
    from app.ai_service import get_setting
    from app.models import Appointment
    from app.ownership import current_business_id, owned_filter, public_business_id

    business_id = current_business_id(request) if request is not None else public_business_id(db)
    today = datetime.combine(date.today(), time.min)
    upcoming = db.query(func.count(Appointment.id)).filter(
        owned_filter(Appointment, business_id),
        Appointment.appointment_time >= today, Appointment.status == "confirmed",
    ).scalar() or 0
    from app.ai_service import get_appointment_minutes
    return {"business_name": get_setting(db, "business_name", settings.business_name), "upcoming_count": upcoming,
            "appointment_minutes": get_appointment_minutes(db, business_id)}
