"""v1.0.9: appointment length is set per business in Admin -> Settings (minutes)."""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _csrf(client):
    page = client.get("/admin/settings")
    assert page.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def _save(client, minutes, **extra):
    data = {"business_name": "Test Clinic", "ai_base_url": "", "ai_api_key": "", "ai_model": "",
            "opening_hour": "9", "closing_hour": "18", "closed_days": "sunday", "holiday_dates": "",
            "appointment_minutes": str(minutes), "csrf_token": _csrf(client)} | extra
    return client.post("/admin/settings", data=data, follow_redirects=False)


def _minutes(business_id=1):
    from app.ai_service import get_appointment_minutes
    from app.database import SessionLocal

    with SessionLocal() as db:
        return get_appointment_minutes(db, business_id)


def _open_day(days_ahead=7):
    day = datetime.now().date() + timedelta(days=days_ahead)
    while day.weekday() == 6:  # closed on Sunday in the test fixture
        day += timedelta(days=1)
    return day.isoformat()


def _book(when, phone, name="Visitor"):
    from app.ai_service import book_appointment_tool
    from app.database import SessionLocal
    from app.models import Conversation

    with SessionLocal() as db:
        conv = Conversation(business_id=1, channel="web")
        db.add(conv)
        db.commit()
        return book_appointment_tool(db, conv.id, name, phone, "Checkup", when)


def _set(minutes, business_id=1):
    from app.ai_service import set_appointment_minutes
    from app.database import SessionLocal

    with SessionLocal() as db:
        set_appointment_minutes(db, business_id, minutes)


# --- settings ---------------------------------------------------------------------

def test_settings_shows_minutes_input_default_60(admin_client):
    page = admin_client.get("/admin/settings").text
    assert "Appointment length (minutes)" in page
    assert re.search(r'name="appointment_minutes" min="5" max="480" step="5"[^>]*value="60"', page)


def test_settings_saves_length(admin_client):
    r = _save(admin_client, 30)
    assert r.status_code == 303 and r.headers["location"] == "/admin/settings?saved=1"
    assert _minutes() == 30
    assert 'value="30"' in admin_client.get("/admin/settings").text
    assert "30 <small" in admin_client.get("/admin/appointments").text  # "New booking length" stat


@pytest.mark.parametrize("bad", ["0", "1000", "abc", "45.5", "-30", "7", "485"])
def test_settings_rejects_invalid_length_and_saves_nothing(admin_client, bad):
    r = _save(admin_client, bad, business_name="Should Not Save")
    assert r.status_code == 303 and r.headers["location"].endswith("error=duration")
    assert _minutes() == 60
    from app.ai_service import get_setting
    from app.database import SessionLocal
    with SessionLocal() as db:
        assert get_setting(db, "business_name") == "Test Clinic"
    assert "Appointment length must be a whole number" in admin_client.get("/admin/settings?error=duration").text


def test_settings_length_requires_csrf(admin_client):
    r = _save(admin_client, 30, csrf_token="wrong")
    assert r.status_code == 403 and _minutes() == 60


def test_length_is_saved_only_for_the_session_business(admin_client):
    from app.database import SessionLocal
    from app.models import Business
    from tests.test_brand_logo_v109 import _as_business

    with SessionLocal() as db:
        db.add(Business(id=2, name="Other Clinic"))
        db.commit()
    token = _csrf(admin_client)
    _as_business(admin_client, 2)
    _save(admin_client, 45, csrf_token=token)
    assert _minutes(2) == 45 and _minutes(1) == 60


def test_demo_cannot_change_length(demo_client):
    page = demo_client.get("/admin/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    demo_client.post("/admin/demo-login", data={"csrf_token": token}, follow_redirects=False)
    settings_page = demo_client.get("/admin/settings").text
    assert re.search(r'name="appointment_minutes"[^>]*readonly', settings_page)
    token = re.search(r'name="csrf_token" value="([^"]+)"', settings_page).group(1)
    r = demo_client.post("/admin/settings", data={"business_name": "X", "appointment_minutes": "30", "csrf_token": token}, follow_redirects=False)
    assert r.status_code == 403


# --- bot replies --------------------------------------------------------------------

@pytest.mark.parametrize("minutes", [30, 90])
def test_bot_and_chat_page_use_configured_length(client, minutes):
    _set(minutes)
    reply = client.post("/chat", data={"message": "How long is an appointment?"}).json()["reply"]
    assert f"{minutes}-minute" in reply and "60" not in reply
    page = client.get("/chat").text
    assert f'data-minutes="{minutes}"' in page and f"Appointments are {minutes} minutes." in page
    # Landing no longer shows the configured length as a hero statistic;
    # the Features section describes the 5–480 minute range instead.
    landing = client.get("/").text
    assert "5–480 minutes" in landing
    assert f"{minutes} min</div>" not in landing

    from app.ai_service import build_system_prompt
    from app.database import SessionLocal
    with SessionLocal() as db:
        prompt = build_system_prompt(db, 1)
    assert f"Appointments are {minutes}-minute slots" in prompt and "60-minute" not in prompt
    last = (datetime(2000, 1, 1, 18) - timedelta(minutes=minutes)).strftime("%H:%M")
    assert f"latest start time is {last}" in prompt


@pytest.mark.parametrize("minutes", [30, 90])
def test_demo_rule_replies_use_length(minutes):
    from app.demo_ai import booking_prompt, local_demo_reply
    assert f"{minutes}-minute" in booking_prompt(minutes)
    assert f"{minutes}-minute" in local_demo_reply("How long is an appointment?", [], minutes)
    assert f"{minutes}-minute" in local_demo_reply("hello", [], minutes)


def test_chat_js_reads_length_from_data_attribute():
    js = (ROOT / "static" / "chat.js").read_text()
    assert "messagesEl.dataset.minutes" in js and "60-minute appointment" not in js
    html = (ROOT / "templates" / "chat.html").read_text()
    assert "Appointments are 60 minutes" not in html


# --- booking ------------------------------------------------------------------------

def test_booking_end_time_uses_length(client):
    _set(30)
    day = _open_day()
    result = _book(f"{day} 10:00", "5550001")
    assert result["success"], result
    assert "10:00 AM – 10:30 AM (30 minutes)" in result["message"]
    from app.database import SessionLocal
    from app.models import Appointment
    with SessionLocal() as db:
        appt = db.get(Appointment, result["appointment_id"])
        assert appt.duration_minutes == 30
        assert appt.end_time == appt.appointment_time + timedelta(minutes=30)
    # with 30 minutes, 10:30 is free right after
    assert _book(f"{day} 10:30", "5550002")["success"]


def test_overlap_uses_each_appointments_own_length(client):
    day = _open_day()
    _set(90)
    assert _book(f"{day} 10:00", "5550011")["success"]       # 10:00-11:30
    _set(30)
    clash = _book(f"{day} 11:00", "5550012")                  # 11:00-11:30 overlaps the 90-minute one
    assert not clash["success"] and "overlaps" in clash["error"]
    assert _book(f"{day} 11:30", "5550013")["success"]       # starts when it ends
    assert _book(f"{day} 9:30", "5550014")["success"]        # 9:30-10:00 ends when it starts


def test_booking_must_end_by_closing_time(client):
    day = _open_day()
    _set(90)
    late = _book(f"{day} 17:00", "5550021")                   # would end 18:30, closing is 18:00
    assert not late["success"]
    assert "must end by 18:00" in late["error"] and "04:30 PM" in late["error"]
    assert _book(f"{day} 16:30", "5550022")["success"]       # ends exactly 18:00
    _set(30)
    other_day = _open_day(8 if datetime.fromisoformat(day).weekday() != 5 else 9)
    assert _book(f"{other_day} 17:30", "5550023")["success"]  # 30 minutes fits before 18:00


def test_changing_length_does_not_alter_old_appointments(client, admin_client):
    day = _open_day()
    first = _book(f"{day} 10:00", "5550031")
    assert first["success"]
    assert _save(admin_client, 30).headers["location"] == "/admin/settings?saved=1"
    from app.database import SessionLocal
    from app.models import Appointment
    with SessionLocal() as db:
        old = db.get(Appointment, first["appointment_id"])
        assert old.duration_minutes == 60 and old.end_time.hour == 11
    rows = admin_client.get("/admin/appointments").text
    assert "60 min</td>" in rows


# --- migration ------------------------------------------------------------------------

def test_old_database_gets_length_column_and_durations(tmp_path):
    from sqlalchemy import create_engine
    from app.database import ensure_schema
    import app.models  # noqa: F401

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE businesses (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, created_at DATETIME)")
    con.execute("INSERT INTO businesses (id, name) VALUES (1, 'Old')")
    con.execute("CREATE TABLE appointments (id INTEGER PRIMARY KEY, customer_name VARCHAR(200) NOT NULL, customer_phone VARCHAR(50), service VARCHAR(200), appointment_time DATETIME NOT NULL, duration_minutes INTEGER, notes TEXT, status VARCHAR(50), created_at DATETIME, conversation_id INTEGER)")
    con.execute("INSERT INTO appointments (customer_name, appointment_time, duration_minutes) VALUES ('A', '2026-01-01 10:00:00', NULL), ('B', '2026-01-01 12:00:00', 45)")
    con.commit()
    con.close()
    for _ in range(2):  # idempotent
        ensure_schema(create_engine(f"sqlite:///{db}"))
    con = sqlite3.connect(db)
    assert con.execute("SELECT appointment_minutes FROM businesses WHERE id = 1").fetchone()[0] == 60
    assert [r[0] for r in con.execute("SELECT duration_minutes FROM appointments ORDER BY id")] == [60, 45]


def test_schema_sql_has_length_column():
    sql = (ROOT.parent / "database" / "schema.sql").read_text()
    assert "appointment_minutes INTEGER NOT NULL DEFAULT 60" in sql


# --- business name on the chat page ----------------------------------------------------

def test_chat_page_uses_business_name(client):
    page = client.get("/chat").text
    assert "<title>Visitor chat · Test Clinic</title>" in page
    assert page.count("Test Clinic") >= 3  # title, top bar, chat header
