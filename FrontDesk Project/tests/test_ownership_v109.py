"""v1.0.9: admin records are loaded by id AND owning business (audit warning fix)."""
from __future__ import annotations

import inspect
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _csrf(client, path="/admin/appointments"):
    page = client.get(path)
    assert page.status_code == 200, page.status_code
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def _seed_two_businesses():
    """Business 1 (the admin's) and business 2 (someone else's), one row each."""
    from app.database import SessionLocal
    from app.models import Appointment, Business, Conversation, KnowledgeItem, Message

    db = SessionLocal()
    try:
        if not db.get(Business, 2):
            db.add(Business(id=2, name="Other Clinic"))
            db.commit()
        when = datetime.now().replace(microsecond=0) + timedelta(days=3)
        own_conv = Conversation(business_id=1, channel="web", customer_name="Own Visitor")
        other_conv = Conversation(business_id=2, channel="web", customer_name="Foreign Visitor")
        db.add_all([own_conv, other_conv])
        db.flush()
        db.add_all([
            Message(conversation_id=own_conv.id, role="user", content="own message"),
            Message(conversation_id=other_conv.id, role="user", content="foreign secret message"),
        ])
        own = Appointment(business_id=1, customer_name="Own Patient", customer_phone="111", service="Checkup", appointment_time=when, status="confirmed")
        other = Appointment(business_id=2, customer_name="Foreign Patient", customer_phone="222", service="Whitening", appointment_time=when + timedelta(hours=2), status="confirmed")
        own_kb = KnowledgeItem(business_id=1, question="Own question?", answer="Own answer")
        other_kb = KnowledgeItem(business_id=2, question="Foreign question?", answer="Foreign answer")
        db.add_all([own, other, own_kb, other_kb])
        db.commit()
        return {"own_appt": own.id, "other_appt": other.id, "own_conv": own_conv.id, "other_conv": other_conv.id, "own_kb": own_kb.id, "other_kb": other_kb.id}
    finally:
        db.close()


def _status(appt_id):
    from app.database import SessionLocal
    from app.models import Appointment

    db = SessionLocal()
    try:
        return db.query(Appointment.status).filter(Appointment.id == appt_id).scalar()
    finally:
        db.close()


# --- appointment status route (the flagged one) -----------------------------------

def test_owner_can_update_own_appointment(admin_client):
    ids = _seed_two_businesses()
    r = admin_client.post(f"/admin/appointments/{ids['own_appt']}/status", data={"status": "completed", "csrf_token": _csrf(admin_client)}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/appointments?updated=1"
    assert _status(ids["own_appt"]) == "completed"


def test_other_business_appointment_is_404_and_unchanged(admin_client):
    ids = _seed_two_businesses()
    r = admin_client.post(f"/admin/appointments/{ids['other_appt']}/status", data={"status": "cancelled", "csrf_token": _csrf(admin_client)}, follow_redirects=False)
    assert r.status_code == 404
    assert _status(ids["other_appt"]) == "confirmed"


def test_missing_appointment_is_404(admin_client):
    r = admin_client.post("/admin/appointments/999999/status", data={"status": "cancelled", "csrf_token": _csrf(admin_client, "/admin/knowledge")}, follow_redirects=False)
    assert r.status_code == 404


def test_anonymous_status_change_redirects_to_login(client):
    ids = _seed_two_businesses()
    r = client.post(f"/admin/appointments/{ids['own_appt']}/status", data={"status": "cancelled"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"
    assert _status(ids["own_appt"]) == "confirmed"


def test_bad_csrf_rejected(admin_client):
    ids = _seed_two_businesses()
    r = admin_client.post(f"/admin/appointments/{ids['own_appt']}/status", data={"status": "cancelled", "csrf_token": "forged"}, follow_redirects=False)
    assert r.status_code == 403
    assert _status(ids["own_appt"]) == "confirmed"


def test_invalid_status_is_422(admin_client):
    ids = _seed_two_businesses()
    r = admin_client.post(f"/admin/appointments/{ids['own_appt']}/status", data={"status": "deleted", "csrf_token": _csrf(admin_client)}, follow_redirects=False)
    assert r.status_code == 422
    assert _status(ids["own_appt"]) == "confirmed"


def test_session_without_business_must_log_in_again(admin_client):
    """Sessions from older builds (no business_id) are not trusted."""
    from starlette.middleware.sessions import SessionMiddleware  # noqa: F401
    import base64
    import json

    import itsdangerous

    signer = itsdangerous.TimestampSigner("test-secret-key-for-pytest-only-not-production")
    payload = base64.b64encode(json.dumps({"user": "admin", "role": "admin", "admin": True}).encode())
    admin_client.cookies.set("frontdesk_session", signer.sign(payload).decode())
    r = admin_client.get("/admin/appointments", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"


# --- every other id-based admin route ------------------------------------------------

def test_other_business_rows_are_404_everywhere(admin_client):
    ids = _seed_two_businesses()
    token = _csrf(admin_client)
    assert admin_client.get(f"/admin/conversations/{ids['other_conv']}").status_code == 404
    assert admin_client.get(f"/admin/conversations/{ids['own_conv']}").status_code == 200
    assert admin_client.post(f"/admin/conversations/{ids['other_conv']}/delete", data={"csrf_token": token}, follow_redirects=False).status_code == 404
    assert admin_client.get(f"/admin/knowledge/{ids['other_kb']}/edit").status_code == 404
    assert admin_client.get(f"/admin/knowledge/{ids['own_kb']}/edit").status_code == 200
    assert admin_client.post(f"/admin/knowledge/{ids['other_kb']}/edit", data={"question": "x", "answer": "y", "csrf_token": token}, follow_redirects=False).status_code == 404
    assert admin_client.post(f"/admin/knowledge/{ids['other_kb']}/delete", data={"csrf_token": token}, follow_redirects=False).status_code == 404

    from app.database import SessionLocal
    from app.models import Conversation, KnowledgeItem

    db = SessionLocal()
    try:
        assert db.get(Conversation, ids["other_conv"]) is not None
        assert db.get(KnowledgeItem, ids["other_kb"]).question == "Foreign question?"
    finally:
        db.close()


def test_lists_search_and_counts_are_scoped(admin_client):
    _seed_two_businesses()
    for path in ("/admin", "/admin/appointments", "/admin/appointments?q=Patient", "/admin/conversations", "/admin/knowledge"):
        page = admin_client.get(path)
        assert page.status_code == 200, path
        assert "Foreign" not in page.text, path
    assert "Own Patient" in admin_client.get("/admin/appointments").text


def test_production_admin_sees_edit_and_status_controls(admin_client):
    ids = _seed_two_businesses()
    assert f'/admin/knowledge/{ids["own_kb"]}/edit' in admin_client.get("/admin/knowledge").text
    assert f'/admin/appointments/{ids["own_appt"]}/status' in admin_client.get("/admin/appointments").text
    assert f'/admin/conversations/{ids["own_conv"]}/delete' in admin_client.get("/admin/conversations").text


def test_public_booking_sets_owner(client):
    from app.ai_service import book_appointment_tool
    from app.database import SessionLocal
    from app.models import Appointment, Conversation

    db = SessionLocal()
    try:
        conv = Conversation(channel="web", visitor_token="t")
        db.add(conv)
        db.commit()
        day = datetime.now() + timedelta(days=7)
        while day.weekday() == 6:
            day += timedelta(days=1)
        result = book_appointment_tool(db, conv.id, "Owner Test", "+1 555 0100", "Checkup", day.strftime("%Y-%m-%d 10:00"))
        assert result["success"], result
        assert db.get(Appointment, result["appointment_id"]).business_id == 1
        assert db.get(Conversation, conv.id).business_id == 1
    finally:
        db.close()


# --- static checks an auditor would run ----------------------------------------------

def test_no_admin_route_loads_by_primary_key_alone():
    from app import app as _app  # noqa: F401
    from routes.admin import appointments, conversations, dashboard, knowledge, settings

    for module in (appointments, conversations, dashboard, knowledge, settings):
        src = inspect.getsource(module)
        assert "db.get(" not in src, module.__name__
        for model in ("Appointment", "Conversation", "KnowledgeItem", "Message"):
            assert f"db.query({model})" not in src, (module.__name__, model)
    src = inspect.getsource(appointments.update_appointment_status)
    assert "get_owned_or_404(db, Appointment, appt_id, request" in src
    assert src.index("demo_blocks_mutation") < src.index("appt.status = status")
    assert "verify_csrf" in src and "require_admin" in src


def test_appointments_list_handler_is_short():
    from app import app as _app  # noqa: F401
    from routes.admin import appointments

    assert len(inspect.getsource(appointments.appointments_list).splitlines()) <= 6


# --- migration of a v1.0.8 database ---------------------------------------------------

V108_SCHEMA = """
CREATE TABLE settings (id INTEGER PRIMARY KEY, key VARCHAR(100) NOT NULL UNIQUE, value TEXT);
CREATE TABLE knowledge_items (id INTEGER PRIMARY KEY, question VARCHAR(500) NOT NULL, answer TEXT NOT NULL, category VARCHAR(100), is_active BOOLEAN, created_at DATETIME);
CREATE TABLE conversations (id INTEGER PRIMARY KEY, channel VARCHAR(50), external_id VARCHAR(200), visitor_token VARCHAR(64), customer_name VARCHAR(200), customer_phone VARCHAR(50), status VARCHAR(50), created_at DATETIME, updated_at DATETIME);
CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, role VARCHAR(20) NOT NULL, content TEXT NOT NULL, created_at DATETIME);
CREATE TABLE appointments (id INTEGER PRIMARY KEY, conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL, customer_name VARCHAR(200) NOT NULL, customer_phone VARCHAR(50), service VARCHAR(200), appointment_time DATETIME NOT NULL, duration_minutes INTEGER, notes TEXT, status VARCHAR(50), created_at DATETIME);
INSERT INTO knowledge_items (question, answer) VALUES ('Old Q', 'Old A');
INSERT INTO conversations (channel) VALUES ('web');
INSERT INTO appointments (conversation_id, customer_name, appointment_time, status) VALUES (1, 'Old Patient', '2099-01-05 10:00:00', 'confirmed');
"""


def test_v108_database_is_migrated_and_backfilled(tmp_path):
    from sqlalchemy import create_engine

    from app.database import ensure_schema
    import app.models  # noqa: F401

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(V108_SCHEMA)
    eng = create_engine(f"sqlite:///{path}")
    ensure_schema(eng)
    ensure_schema(eng)  # idempotent
    eng.dispose()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT id FROM businesses").fetchall() == [(1,)]
        for table in ("appointments", "conversations", "knowledge_items"):
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            assert "business_id" in cols, table
            assert conn.execute(f"SELECT DISTINCT business_id FROM {table}").fetchall() == [(1,)], table


@pytest.mark.parametrize("kind", ["schema"])
def test_schema_sql_has_business_table(kind):
    sql = (ROOT.parent / "database" / "schema.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS businesses" in sql
    assert sql.count("REFERENCES businesses(id)") == 3


# --- demo sandbox: demo_blocks_mutation + demo_created for appointments ---------------

def _enter_demo(client):
    page = client.get("/admin/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    r = client.post("/admin/demo-login", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin"



def test_sidebar_visitor_chat_link_markup_is_valid(admin_client):
    """v1.0.9: a malformed </span> tag made 'Open visitor chat' wrap onto several lines."""
    page = admin_client.get("/admin").text
    assert "</spantarget" not in page
    assert '<span class="nav-dot"></span>Open visitor chat' in page


def test_demo_seeded_appointment_status_can_change_in_private_sandbox(demo_client):
    _enter_demo(demo_client)
    page = demo_client.get("/admin/appointments")
    assert "Read-only demo row" not in page.text
    seeded = [int(x) for x in re.findall(r"#(\d+)</div>", page.text)]
    assert seeded and f"/admin/appointments/{seeded[0]}/status" in page.text
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    r = demo_client.post(f"/admin/appointments/{seeded[0]}/status", data={"status": "completed", "csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert "Appointment status updated" in demo_client.get(r.headers["location"]).text
