"""Dashboard metrics for the admin home page.

Every count and list is scoped to the business owned by the logged-in admin
(see app/ownership.py). Kept out of the route so the handler stays short.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models import Appointment, Conversation, KnowledgeItem, Message
from app.ownership import current_business_id, owned_filter, owned_messages_query, owned_query


def dashboard_metrics(db: Session, request: Request) -> dict:
    """KPIs, recent conversations, upcoming bookings and 7-day activity."""
    business_id = current_business_id(request)
    own_appt = owned_filter(Appointment, business_id)
    own_conv = owned_filter(Conversation, business_id)
    today = datetime.combine(date.today(), time.min)
    tomorrow = today + timedelta(days=1)
    month_start = today.replace(day=1)
    conv_count = db.query(func.count(Conversation.id)).filter(own_conv).scalar() or 0
    msg_count = owned_messages_query(db, request).with_entities(func.count(Message.id)).scalar() or 0
    appt_count = db.query(func.count(Appointment.id)).filter(own_appt).scalar() or 0
    upcoming_count = db.query(func.count(Appointment.id)).filter(own_appt, Appointment.appointment_time >= today, Appointment.status == "confirmed").scalar() or 0
    today_count = db.query(func.count(Appointment.id)).filter(own_appt, Appointment.appointment_time >= today, Appointment.appointment_time < tomorrow, Appointment.status != "cancelled").scalar() or 0
    completed_count = db.query(func.count(Appointment.id)).filter(own_appt, Appointment.status == "completed").scalar() or 0
    attended_conv = db.query(func.count(func.distinct(Appointment.conversation_id))).filter(own_appt, Appointment.status != "cancelled").scalar() or 0
    conversion = round(attended_conv * 100 / conv_count) if conv_count else 0
    this_month = db.query(func.count(Appointment.id)).filter(own_appt, Appointment.appointment_time >= month_start).scalar() or 0
    kb_count = db.query(func.count(KnowledgeItem.id)).filter(owned_filter(KnowledgeItem, business_id)).scalar() or 0
    recent = owned_query(db, Conversation, request).options(selectinload(Conversation.messages)).order_by(Conversation.updated_at.desc()).limit(5).all()
    upcoming = owned_query(db, Appointment, request).filter(Appointment.appointment_time >= today, Appointment.status == "confirmed").order_by(Appointment.appointment_time.asc()).limit(5).all()
    # Real daily conversation counts for the last seven days, normalized in Python.
    activity_start = today - timedelta(days=6)
    counts = dict(db.query(func.date(Conversation.created_at), func.count(Conversation.id)).filter(own_conv, Conversation.created_at >= activity_start).group_by(func.date(Conversation.created_at)).all())
    activity = [{"label": (activity_start + timedelta(days=i)).strftime("%a"), "count": counts.get((activity_start + timedelta(days=i)).date().isoformat(), 0)} for i in range(7)]
    max_activity = max([1] + [entry["count"] for entry in activity])
    return {
        "conv_count": conv_count, "msg_count": msg_count,
        "appt_count": appt_count, "upcoming_count": upcoming_count, "today_count": today_count,
        "completed_count": completed_count, "this_month": this_month, "kb_count": kb_count,
        "conversion": conversion, "recent": recent, "upcoming": upcoming,
        "activity": activity, "max_activity": max_activity,
    }
