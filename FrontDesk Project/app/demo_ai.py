"""Deterministic demonstrations of receptionist workflows; no network access."""
from __future__ import annotations

import re
from app.models import KnowledgeItem


def booking_prompt(minutes: int = 60) -> str:
    return (
        f"I can reserve a {minutes}-minute appointment. Please provide your name, phone number, "
        "preferred service and date/time in one message. For example: Sam Lee, 555-0199, "
        "dental checkup, next Monday at 10am (or a date such as 10 November at 5pm)."
    )


BOOKING_PROMPT = booking_prompt(60)  # backwards compatible constant


def local_demo_reply(message: str, knowledge: list[KnowledgeItem], minutes: int = 60) -> str:
    from app.ai_service import appointment_length_reply, is_length_question

    text = re.sub(r"\s+", " ", message.strip().lower())
    if is_length_question(text):
        return appointment_length_reply(minutes)
    for item in knowledge:
        words = [w for w in re.findall(r"[a-z]{4,}", item.question.lower()) if w not in {"what", "your", "with", "have", "from", "about", "should"}]
        if any(word in text for word in words):
            return item.answer
    if any(w in text for w in {"book", "appointment", "schedule", "reserve"}):
        return booking_prompt(minutes)
    if any(w in text for w in {"hello", "hi", "hey"}):
        return ("Welcome to Lumen Dental Studio. I can help with opening hours, treatments, "
                f"appointment preparation, or booking a {minutes}-minute time.")
    return ("This guided demo can answer questions about hours, treatments, appointment length "
            "and booking. Try: What time are you open?")
