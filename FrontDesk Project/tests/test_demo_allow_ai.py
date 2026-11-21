"""DEMO_ALLOW_AI: live host-provided AI on an otherwise isolated public demo."""
from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


FAKE_KEY = "sk-demo-allow-ai-test-key-do-not-leak"
FAKE_BASE = "http://127.0.0.1:9/v1"  # unused when httpx is mocked
ORIGINAL_GREEN = "AI calls, account credentials, setup and configuration edits are disabled."
LIVE_GREEN = "AI replies are live (limited per session). Account credentials, setup and configuration edits are disabled."


def csrf(client):
    page = client.get("/admin/login")
    assert page.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def enter_demo(client):
    token = csrf(client)
    response = client.post("/admin/demo-login", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    return client


@pytest.fixture()
def allow_ai_client(tmp_path, monkeypatch):
    import sys

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FRONTDESK_TESTING", "1")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_ALLOW_AI", "true")
    monkeypatch.setenv("DEMO_SEED", "pytest-allow-ai")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-pytest-only-not-production")
    monkeypatch.setenv("HTTPS_ONLY", "false")
    monkeypatch.setenv("AI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("AI_BASE_URL", FAKE_BASE)
    monkeypatch.setenv("AI_MODEL", "mock-demo-model")
    monkeypatch.setenv("DEMO_AI_MAX_MESSAGES", "30")
    monkeypatch.setenv("DEMO_AI_DAILY_LIMIT", "500")
    for name in ("ADMIN_USERNAME", "ADMIN_PASSWORD", "SETUP_TOKEN"):
        monkeypatch.setenv(name, "")
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app.") or mod == "main" or mod == "routes" or mod.startswith("routes."):
            del sys.modules[mod]
    from app.demo_ai_limits import reset_demo_ai_limits

    reset_demo_ai_limits()
    from app import app as fastapi_app
    from fastapi.testclient import TestClient

    with TestClient(fastapi_app, base_url="http://demo-ai.test") as c:
        yield c
    reset_demo_ai_limits()


def _completion(content: str = "MOCK-AI: we are open 9 AM to 6 PM.", tool=None):
    message = {"role": "assistant", "content": content}
    if tool:
        message["tool_calls"] = [tool]
        message["content"] = ""
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"choices": [{"message": message}]}
    return response


def test_login_copy_unchanged_without_allow_ai_flag(demo_client):
    page = demo_client.get("/admin/login")
    assert page.status_code == 200
    assert "Enter Admin demo" in page.text
    assert "A fresh sandbox for each review session" in page.text
    assert "Private account access" in page.text
    assert ORIGINAL_GREEN in page.text
    assert "AI replies are live" not in page.text
    assert FAKE_KEY not in page.text


def test_login_copy_mentions_live_ai_only_when_flag_is_on(allow_ai_client):
    page = allow_ai_client.get("/admin/login")
    assert page.status_code == 200
    assert "Enter Admin demo" in page.text
    assert "A fresh sandbox for each review session" in page.text
    assert "Private account access" in page.text
    assert LIVE_GREEN in page.text
    assert ORIGINAL_GREEN not in page.text
    assert FAKE_KEY not in page.text
    assert FAKE_BASE not in page.text
    assert "mock-demo-model" not in page.text


def test_visitor_chat_uses_host_ai_when_allowed(allow_ai_client):
    client = MagicMock()
    client.post = AsyncMock(return_value=_completion())
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    with patch("app.ai_service.httpx.AsyncClient", return_value=client):
        response = allow_ai_client.post("/chat", data={"message": "What are your opening hours?"})
    assert response.status_code == 200
    body = response.json()
    assert "MOCK-AI: we are open 9 AM to 6 PM." in body["reply"]
    assert FAKE_KEY not in body["reply"]
    assert FAKE_KEY not in response.text
    assert client.post.await_count >= 1
    sent = client.post.await_args
    assert sent.args[0].endswith("/chat/completions")
    headers = sent.kwargs["headers"]
    assert headers["Authorization"] == f"Bearer {FAKE_KEY}"
    assert sent.kwargs["json"]["max_tokens"] == 400
    assert sent.kwargs["json"]["model"] == "mock-demo-model"


def test_scripted_fallback_when_session_cap_is_reached(allow_ai_client, monkeypatch):
    from app.config import settings
    from app.demo_ai_limits import reset_demo_ai_limits

    monkeypatch.setattr(settings, "demo_ai_max_messages", 1)
    reset_demo_ai_limits()
    client = MagicMock()
    client.post = AsyncMock(return_value=_completion("MOCK-AI first"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    with patch("app.ai_service.httpx.AsyncClient", return_value=client):
        first = allow_ai_client.post("/chat", data={"message": "Hello there"})
        second = allow_ai_client.post("/chat", data={"message": "What are your opening hours?"})
    assert first.status_code == 200 and "MOCK-AI first" in first.json()["reply"]
    assert second.status_code == 200
    reply = second.json()["reply"]
    assert "live AI preview has reached its limit" in reply
    assert "9 AM to 6 PM" in reply
    assert "MOCK-AI first" not in reply
    assert client.post.await_count == 1
    assert FAKE_KEY not in reply


def test_scripted_fallback_when_input_exceeds_demo_limit(allow_ai_client, monkeypatch):
    from app.config import settings
    from app.demo_ai_limits import reset_demo_ai_limits

    monkeypatch.setattr(settings, "demo_ai_max_input_length", 20)
    reset_demo_ai_limits()
    with patch("app.ai_service.httpx.AsyncClient", side_effect=AssertionError("network forbidden")):
        response = allow_ai_client.post("/chat", data={"message": "What are your opening hours today please?"})
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "live AI preview has reached its limit" in reply
    assert "9 AM to 6 PM" in reply


def test_key_is_never_leaked_in_html_js_or_errors(allow_ai_client):
    enter_demo(allow_ai_client)
    pages = [
        allow_ai_client.get("/admin/login"),
        allow_ai_client.get("/admin"),
        allow_ai_client.get("/admin/settings"),
        allow_ai_client.get("/chat"),
        allow_ai_client.get("/"),
    ]
    for page in pages:
        assert page.status_code == 200, page.url
        assert FAKE_KEY not in page.text
        assert "sk-demo-allow-ai" not in page.text
    settings_page = pages[2]
    assert 'name="ai_api_key"' in settings_page.text
    assert FAKE_BASE not in settings_page.text
    assert "mock-demo-model" not in settings_page.text
    # Simulate a provider exception that includes the key, and ensure it is stripped.
    class Boom(Exception):
        def __str__(self):
            return f"upstream rejected {FAKE_KEY} for this request"

    failing = MagicMock()
    failing.post = AsyncMock(side_effect=Boom())
    failing.__aenter__ = AsyncMock(return_value=failing)
    failing.__aexit__ = AsyncMock(return_value=None)
    with patch("app.ai_service.httpx.AsyncClient", return_value=failing):
        response = allow_ai_client.post("/chat", data={"message": "Tell me a secret"})
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert FAKE_KEY not in reply
    assert "[redacted]" in reply or "could not generate" in reply.lower()


def test_settings_cannot_change_ai_config_in_demo(allow_ai_client):
    enter_demo(allow_ai_client)
    page = allow_ai_client.get("/admin/settings")
    csrf_value = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    values = {
        "business_name": "Injected production name",
        "ai_base_url": "https://evil.invalid/v1",
        "ai_api_key": "sk-injected-by-reviewer",
        "ai_model": "injected-model",
        "opening_hour": "8",
        "closing_hour": "18",
        "closed_days": "sunday",
        "holiday_dates": "",
        "csrf_token": csrf_value,
    }
    assert allow_ai_client.post("/admin/settings", data=values).status_code == 403
    from app.ai_service import get_ai_config, get_setting
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        assert get_setting(db, "business_name") == "Lumen Dental Studio"
        assert not get_setting(db, "ai_api_key", "")
        assert get_setting(db, "ai_model") == "local-demo" or not get_setting(db, "ai_base_url", "")
        config = get_ai_config(db)
        assert config["api_key"] == FAKE_KEY
        assert config["base_url"] == FAKE_BASE
        assert config["model"] == "mock-demo-model"
        assert "sk-injected-by-reviewer" not in (get_setting(db, "ai_api_key", "") or "")
    finally:
        db.close()


def test_live_ai_booking_writes_only_to_the_sandbox(allow_ai_client):
    """A tool-call booking from the host AI must land in the demo sandbox only."""
    import json

    tool = {
        "id": "call_1",
        "function": {
            "name": "book_appointment",
            "arguments": json.dumps({
                "customer_name": "Demo Visitor",
                "customer_phone": "555-0199",
                "service": "dental checkup",
                "appointment_time_text": "next Monday at 3pm",
            }),
        },
    }
    first = _completion(tool=tool)
    follow = _completion("Appointment confirmed for Demo Visitor in the sandbox.")
    client = MagicMock()
    client.post = AsyncMock(side_effect=[first, follow])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    with patch("app.ai_service.httpx.AsyncClient", return_value=client):
        response = allow_ai_client.post(
            "/chat", data={"message": "Please book Demo Visitor, 555-0199, dental checkup, next Monday at 3pm"},
        )
    assert response.status_code == 200
    assert "Demo Visitor" in response.json()["reply"]
    assert FAKE_KEY not in response.json()["reply"]

    import base64
    import itsdangerous
    from app.config import settings
    from app.database import bind_for_session
    from app.models import Appointment

    cookie = allow_ai_client.cookies.get("frontdesk_demo_session")
    payload = json.loads(base64.urlsafe_b64decode(
        itsdangerous.TimestampSigner(settings.secret_key + "|frontdesk-demo|" + settings.demo_seed).unsign(cookie).decode() + "=="
    ))
    _, ScopedSession = bind_for_session(payload.get("demo_scope"))
    db = ScopedSession()
    try:
        appointment = db.query(Appointment).filter_by(customer_name="Demo Visitor", customer_phone="555-0199").one()
        assert appointment.service == "dental checkup"
        assert "demo-pytest-allow-ai" in settings.database_url or "demo-" in settings.database_url
    finally:
        db.close()
