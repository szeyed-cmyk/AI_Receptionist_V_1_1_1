"""Appointment queries used by the admin appointment routes.

Keeps route handlers short. Every query here is ownership-scoped to the
business of the logged-in admin (see app/ownership.py).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment
from app.ownership import current_business_id, owned_filter, owned_query
from app.web import LIKE_ESCAPE, clean_query, like_term, page_params, pagination

APPOINTMENT_STATUSES = {"confirmed", "cancelled", "completed"}


def filtered_appointments(db: Session, request: Request, status: str = "", q: str = ""):
    """Owned appointments, optionally filtered by status and a search term."""
    query = owned_query(db, Appointment, request)
    if status in APPOINTMENT_STATUSES:
        query = query.filter(Appointment.status == status)
    if q.strip():
        term = like_term(q)
        query = query.filter(
            Appointment.customer_name.ilike(term, escape=LIKE_ESCAPE)
            | Appointment.customer_phone.ilike(term, escape=LIKE_ESCAPE)
            | Appointment.service.ilike(term, escape=LIKE_ESCAPE)
        )
    return query


def appointment_counts(db: Session, business_id: int) -> dict:
    """Confirmed and today's (non-cancelled) appointment counts for one business."""
    today = datetime.combine(date.today(), time.min)
    owned = owned_filter(Appointment, business_id)
    confirmed = db.query(func.count(Appointment.id)).filter(owned, Appointment.status == "confirmed").scalar() or 0
    today_count = db.query(func.count(Appointment.id)).filter(
        owned,
        Appointment.appointment_time >= today,
        Appointment.appointment_time < today + timedelta(days=1),
        Appointment.status != "cancelled",
    ).scalar() or 0
    return {"confirmed_count": confirmed, "today_count": today_count}


def appointments_page(db: Session, request: Request, status: str = "", q: str = "") -> dict:
    """Template context for one page of the appointment list."""
    _, offset = page_params(request)
    query = filtered_appointments(db, request, status, q)
    total = query.count()
    items = query.order_by(Appointment.appointment_time.asc()).offset(offset).limit(settings.page_size).all()
    return {
        "items": items,
        "status": status,
        "q": clean_query(q),
        **appointment_counts(db, current_business_id(request)),
        **pagination(request, total),
    }
