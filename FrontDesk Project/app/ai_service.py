from typing import Optional, List, Dict, Any
import httpx
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Setting, KnowledgeItem, Message, Appointment, Conversation

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def get_setting(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    item = db.query(Setting).filter(Setting.key == key).first()
    return item.value if item and item.value else default


def set_setting(db: Session, key: str, value: str):
    item = db.query(Setting).filter(Setting.key == key).first()
    if item:
        item.value = value
    else:
        item = Setting(key=key, value=value)
        db.add(item)
    db.commit()


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def redact_secrets(text: str, *secrets: str | None) -> str:
    """Strip host secrets from any string that might be shown or logged."""
    out = text or ""
    for secret in secrets:
        value = (secret or "").strip()
        if value and value in out:
            out = out.replace(value, "[redacted]")
    return out


def get_ai_config(db: Session) -> dict:
    from app.crypto import decrypt_secret

    # In demo mode the key may only come from the host environment, and only
    # when DEMO_ALLOW_AI=true. Seeded DB values (including "local-demo") must
    # never override or expose the operator's provider settings.
    if settings.demo_mode:
        if settings.demo_allow_ai:
            return {
                "base_url": (settings.ai_base_url or "").strip() or DEFAULT_OPENAI_BASE_URL,
                "api_key": (settings.ai_api_key or "").strip(),
                "model": (settings.ai_model or "").strip() or DEFAULT_OPENAI_MODEL,
            }
        return {"base_url": "", "api_key": "", "model": ""}

    raw_key = get_setting(db, "ai_api_key", settings.ai_api_key or "") or ""
    return {
        "base_url": get_setting(db, "ai_base_url", settings.ai_base_url),
        "api_key": decrypt_secret(raw_key) if raw_key else "",
        "model": get_setting(db, "ai_model", settings.ai_model),
    }


def set_ai_api_key(db: Session, plain_key: str) -> None:
    """Store the AI API key encrypted at rest (Fernet derived from SECRET_KEY)."""
    from app.crypto import encrypt_secret

    set_setting(db, "ai_api_key", encrypt_secret(plain_key) if plain_key else "")


MIN_APPOINTMENT_MINUTES = 5
MAX_APPOINTMENT_MINUTES = 480
DEFAULT_APPOINTMENT_MINUTES = 60


def get_appointment_minutes(db: Session, business_id: int | None = None) -> int:
    """Length of NEW appointments for a business (Admin -> Settings), default 60."""
    from app.models import Business
    from app.ownership import public_business_id

    business_id = business_id or public_business_id(db)
    value = db.query(Business.appointment_minutes).filter(Business.id == business_id).scalar()
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_APPOINTMENT_MINUTES
    if not MIN_APPOINTMENT_MINUTES <= value <= MAX_APPOINTMENT_MINUTES:
        return DEFAULT_APPOINTMENT_MINUTES
    return value


def set_appointment_minutes(db: Session, business_id: int, minutes: int) -> None:
    from app.models import Business

    business = db.query(Business).filter(Business.id == business_id).first()
    if business is not None:
        business.appointment_minutes = int(minutes)
        db.commit()


def parse_appointment_minutes(raw: str) -> int:
    """Validate the settings form value: whole minutes, 5-480, multiples of 5."""
    value = int(str(raw).strip())
    if not MIN_APPOINTMENT_MINUTES <= value <= MAX_APPOINTMENT_MINUTES or value % 5:
        raise ValueError("appointment length out of range")
    return value


def appointment_length_reply(minutes: int) -> str:
    return (f"Every appointment reserves a full {minutes}-minute slot. To book, send your name, "
            "phone number, the service and your preferred date and time, and I will check availability.")


_LENGTH_WORDS = ("how long", "length", "duration", "how many minutes", "how much time")


def is_length_question(message: str) -> bool:
    text = " ".join((message or "").lower().split())
    return any(word in text for word in _LENGTH_WORDS)


def get_business_hours(db: Session) -> Dict[str, Any]:
    """Return opening/closing hours, closed weekdays, and holiday dates from settings.

    Defaults match seed.sql: Monday–Saturday 09:00–18:00, closed Sunday.
    """
    try:
        opening = int(get_setting(db, "opening_hour", "9") or "9")
    except (TypeError, ValueError):
        opening = 9
    try:
        closing = int(get_setting(db, "closing_hour", "18") or "18")
    except (TypeError, ValueError):
        closing = 18
    opening = max(0, min(23, opening))
    closing = max(1, min(24, closing))
    if closing <= opening:
        opening, closing = 9, 18

    closed_raw = (get_setting(db, "closed_days", "sunday") or "sunday").lower()
    closed_days = {d.strip() for d in closed_raw.split(",") if d.strip()}

    holidays_raw = get_setting(db, "holiday_dates", "") or ""
    holidays = {h.strip() for h in holidays_raw.split(",") if h.strip()}

    return {
        "opening_hour": opening,
        "closing_hour": closing,
        "closed_days": closed_days,
        "holidays": holidays,
    }


def _today_label() -> str:
    from app.datetime_parse import business_now

    n = business_now()
    return f"{n.strftime('%A')}, {n.day} {n.strftime('%B %Y')}"


def build_system_prompt(db: Session, business_id: int | None = None) -> str:
    from app.ownership import owned_filter, public_business_id

    business_id = business_id or public_business_id(db)
    business_name = get_setting(db, "business_name", settings.business_name)
    knowledge = db.query(KnowledgeItem).filter(owned_filter(KnowledgeItem, business_id), KnowledgeItem.is_active.is_(True)).all()
    kb_text = "\n".join([f"- Q: {k.question}\n  A: {k.answer}" for k in knowledge]) or "No specific FAQs yet."

    hours = get_business_hours(db)
    open_h = hours["opening_hour"]
    close_h = hours["closing_hour"]
    minutes = get_appointment_minutes(db, business_id)
    example_start = datetime(2000, 1, 1, 10, 0)
    example_end = example_start + timedelta(minutes=minutes)
    last_start = datetime(2000, 1, 1) + timedelta(hours=close_h) - timedelta(minutes=minutes)
    closed = sorted(hours["closed_days"]) or ["sunday"]
    open_days = [d for d in DAY_NAMES if d not in hours["closed_days"]]
    open_label = ", ".join(d.title() for d in open_days) if open_days else "None"
    closed_label = ", ".join(d.title() for d in closed)
    holiday_note = (
        f"Holiday dates (closed): {', '.join(sorted(hours['holidays']))}."
        if hours["holidays"]
        else "No holiday dates configured."
    )

    return f"""You are a helpful AI receptionist for {business_name}.
Your job is to:
1. Answer questions about the business using the knowledge base below.
2. Help customers book appointments.
3. Collect name, phone, service, and preferred date/time when booking.
4. Be polite, concise, and professional.
5. If you cannot help, ask the customer to leave their name and phone so the business can follow up.

Knowledge Base:
{kb_text}

IMPORTANT BOOKING RULES:
- Today is {_today_label()} (business timezone). Pass the customer's date to the tool as YYYY-MM-DD plus the time (e.g. "2026-11-10 17:00") or in their own words. Never state or compute a weekday yourself; use the weekday in the tool result.
- If the tool asks for clarification (ambiguous or invalid date, missing time), ask the customer exactly that.
- Appointments are {minutes}-minute slots (example: 10:00 AM – {example_end.strftime('%I:%M %p')}). If asked how long an appointment is, answer {minutes} minutes. This length overrides any other length mentioned in the knowledge base.
- When you have name, phone, service, and a clear date/time, call the book_appointment tool.
- Do not claim an appointment is confirmed until the tool returns success.
- If the tool returns an error (time already booked, overlapping, closed day, holiday, or outside hours), tell the customer and ask for a different time.
- After the tool succeeds, confirm the booking with the time range (start – end).
- Business hours: {open_label}, {open_h}:00 to {close_h}:00. Closed: {closed_label}.
- {holiday_note}
- Do not book appointments before {open_h}:00. Every appointment must end by {close_h}:00, so the latest start time is {last_start.strftime('%H:%M')}.
- A phone number that already has a confirmed appointment cannot book another (duplicate-phone rule). Ask for a different number or cancel the existing booking first.
- Respond in the same language the customer uses.
"""


def parse_datetime(text: str) -> Optional[datetime]:
    """Backward-compatible wrapper: strict parse, None when unclear."""
    from app.datetime_parse import parse_booking_datetime

    return parse_booking_datetime(text)[0]


def book_appointment_tool(
    db: Session,
    conversation_id: int,
    customer_name: str,
    customer_phone: str,
    service: str,
    appointment_time_text: str,
) -> Dict[str, Any]:
    """Tool the AI can call to actually create an appointment."""
    from app.datetime_parse import parse_booking_datetime
    from app.ownership import owned_filter, public_business_id

    # The new appointment belongs to the same business as its conversation;
    # duplicate/overlap checks only look at that business's appointments.
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first() if conversation_id else None
    business_id = conv.business_id if conv is not None and conv.business_id else public_business_id(db)

    # Weekday/closed-day checks use the validated calendar date only.
    dt, parse_error = parse_booking_datetime(appointment_time_text)
    if not dt:
        return {"success": False, "error": parse_error or "Could not understand the date/time."}

    hours = get_business_hours(db)
    day_name = DAY_NAMES[dt.weekday()]

    if day_name in hours["closed_days"]:
        return {"success": False, "error": f"We are closed on {day_name.title()}s."}

    date_key = dt.strftime("%Y-%m-%d")
    if date_key in hours["holidays"]:
        return {"success": False, "error": "We are closed on that date (holiday)."}

    open_h = hours["opening_hour"]
    close_h = hours["closing_hour"]
    duration = get_appointment_minutes(db, business_id)
    new_end = dt + timedelta(minutes=duration)
    if dt.hour < open_h or dt.hour >= close_h:
        return {
            "success": False,
            "error": f"Please choose a time between {open_h}:00 and {close_h}:00.",
        }
    closing_at = datetime.combine(dt.date(), datetime.min.time()) + timedelta(hours=close_h)
    if new_end > closing_at:
        latest = closing_at - timedelta(minutes=duration)
        return {
            "success": False,
            "error": (f"Appointments are {duration} minutes and must end by {close_h}:00. "
                      f"The latest start time that day is {latest.strftime('%I:%M %p')}. Please choose an earlier time."),
        }

    # Duplicate phone check: one confirmed appointment per phone number
    phone_clean = "".join(ch for ch in (customer_phone or "") if ch.isdigit())
    if phone_clean:
        existing_phone = (
            db.query(Appointment)
            .filter(owned_filter(Appointment, business_id), Appointment.status == "confirmed")
            .all()
        )
        for existing in existing_phone:
            existing_clean = "".join(ch for ch in (existing.customer_phone or "") if ch.isdigit())
            if existing_clean and existing_clean == phone_clean:
                return {
                    "success": False,
                    "error": (
                        f"This phone number ({customer_phone}) is already used for an existing appointment. "
                        "Please provide a different phone number."
                    ),
                }

    # Conflict check: the new booking uses the current length; each existing
    # booking keeps the length it was booked with.

    existing_appointments = (
        db.query(Appointment)
        .filter(owned_filter(Appointment, business_id), Appointment.status == "confirmed")
        .all()
    )
    for existing in existing_appointments:
        existing_end = existing.appointment_time + timedelta(minutes=existing.duration_minutes or 60)
        # Overlap if new start < existing end AND existing start < new end
        if dt < existing_end and existing.appointment_time < new_end:
            return {
                "success": False,
                "error": (
                    f"Sorry, {dt.strftime('%I:%M %p')}–{new_end.strftime('%I:%M %p')} "
                    f"overlaps with an existing appointment. Please choose a different time."
                ),
            }

    appt = Appointment(
        business_id=business_id,
        conversation_id=conversation_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        service=service,
        appointment_time=dt,
        duration_minutes=duration,
        status="confirmed",
    )
    db.add(appt)

    # Also store name/phone on conversation
    if conv:
        conv.customer_name = customer_name
        conv.customer_phone = customer_phone

    db.commit()
    db.refresh(appt)

    return {
        "success": True,
        "appointment_id": appt.id,
        "confirmed_date": dt.strftime("%Y-%m-%d"),
        "confirmed_time": f"{dt.strftime('%A, %d %B %Y')} {dt.strftime('%I:%M %p')} – {new_end.strftime('%I:%M %p')}",
        "message": (f"Appointment confirmed for {customer_name} on {dt.strftime('%A, %d %B %Y')}, "
                    f"{dt.strftime('%I:%M %p')} – {new_end.strftime('%I:%M %p')} ({duration} minutes)."),
    }


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment once you have the customer's name, phone, service, and preferred date/time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Full name of the customer"},
                    "customer_phone": {"type": "string", "description": "Phone number"},
                    "service": {"type": "string", "description": "Service requested"},
                    "appointment_time_text": {
                        "type": "string",
                        "description": "Date and time, preferably 'YYYY-MM-DD HH:MM' (24h), or the customer's words e.g. '10 November at 5pm'. Never include a guessed weekday.",
                    },
                },
                "required": ["customer_name", "customer_phone", "service", "appointment_time_text"],
            },
        },
    }
]


async def generate_reply(db: Session, conversation_id: int, user_message: str, max_tokens: int | None = None) -> str:
    config = get_ai_config(db)
    def _safe(text: str) -> str:
        return redact_secrets(text, config.get("api_key"), settings.ai_api_key)

    if not config["api_key"]:
        if is_length_question(user_message):
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            return appointment_length_reply(get_appointment_minutes(db, conv.business_id if conv else None))
        return (
            "AI is not configured yet. Please ask the business owner to add an API key "
            "in the admin settings. You can still leave a message and someone will reply."
        )

    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(20)
        .all()
    )

    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    messages: List[Dict[str, Any]] = [{"role": "system", "content": build_system_prompt(db, conv.business_id if conv else None)}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    url = config["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    token_limit = 600 if max_tokens is None else max(16, int(max_tokens))
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": token_limit,
        "tools": TOOLS,
        "tool_choice": "auto",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            message = choice["message"]

            # Handle tool calls safely
            if message.get("tool_calls"):
                try:
                    tool_call = message["tool_calls"][0]
                    fn = tool_call.get("function", {})
                    if fn.get("name") == "book_appointment":
                        raw_args = fn.get("arguments") or "{}"
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        result = book_appointment_tool(
                            db=db,
                            conversation_id=conversation_id,
                            customer_name=str(args.get("customer_name", "")),
                            customer_phone=str(args.get("customer_phone", "")),
                            service=str(args.get("service", "")),
                            appointment_time_text=str(args.get("appointment_time_text", "")),
                        )

                        messages.append(message)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.get("id", "call_1"),
                                "content": json.dumps(result),
                            }
                        )

                        follow_payload = {
                            "model": config["model"],
                            "messages": messages,
                            "temperature": 0.3,
                            "max_tokens": min(400, token_limit),
                        }
                        follow_resp = await client.post(url, json=follow_payload, headers=headers)
                        follow_resp.raise_for_status()
                        follow_data = follow_resp.json()
                        return _safe(follow_data["choices"][0]["message"]["content"].strip())
                except (json.JSONDecodeError, KeyError, IndexError, ValueError, TypeError) as tool_err:
                    # Fall back to a plain reply if tool handling fails
                    return _safe(message.get("content", "").strip() or ("I had trouble booking that. Could you confirm the date, time, name, and phone again? (%s)" % type(tool_err).__name__))

            return _safe(message.get("content", "").strip() or "I'm not sure how to respond. Could you rephrase?")

    except httpx.HTTPStatusError as e:
        # Some models reject the tools parameter. Retry once without tools.
        if e.response.status_code in (400, 404) and "tools" in payload:
            try:
                payload.pop("tools", None)
                payload.pop("tool_choice", None)
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp2 = await client.post(url, json=payload, headers=headers)
                    resp2.raise_for_status()
                    data2 = resp2.json()
                    return _safe(data2["choices"][0]["message"]["content"].strip())
            except Exception:
                pass
        return _safe("AI service error ({0}). Please check the API key and model.".format(e.response.status_code))
    except Exception as e:
        detail = redact_secrets(f"{type(e).__name__}: {str(e)[:120]}", config.get("api_key"), settings.ai_api_key)
        return _safe(f"Sorry, I could not generate a reply right now. ({detail})")
