"""In-process caps for live AI calls on a public demo instance.

These limits exist so a shared host-provided API key cannot be exhausted by
one visitor. They are process-local (use a single worker). When a cap is
hit, chat falls back to the existing scripted demo replies — it does not
return the key, and it does not 429 solely because of these AI caps.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Request

from app.config import settings
from app.security import client_ip, rate_limit

FALLBACK_NOTE = (
    "The live AI preview has reached its limit for now. "
    "Here is a guided demo reply instead."
)

# session_key -> number of live AI turns consumed in this process
_SESSION_MESSAGES: dict[str, int] = defaultdict(int)
# UTC date ISO -> global live AI turns
_DAILY: dict[str, int] = defaultdict(int)


def reset_demo_ai_limits() -> None:
    """Test helper: clear process-local counters."""
    _SESSION_MESSAGES.clear()
    _DAILY.clear()


def _session_key(request: Request) -> str:
    return (
        request.session.get("demo_scope")
        or request.session.get("visitor_token")
        or "anon"
    )


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def consume_demo_ai_turn(request: Request, message: str) -> tuple[bool, str]:
    """Reserve one live AI turn. Return (allowed, reason_if_denied)."""
    max_input = max(1, int(settings.demo_ai_max_input_length or 1000))
    if len(message or "") > max_input:
        return False, "input"

    ip = client_ip(request)
    if not rate_limit(
        "demo-ai-ip",
        ip,
        max(1, int(settings.demo_ai_ip_max or 10)),
        max(1, int(settings.demo_ai_ip_window_sec or 60)),
    ):
        return False, "ip-rate"

    session = _session_key(request)
    if not rate_limit(
        "demo-ai-session",
        session,
        max(1, int(settings.demo_ai_session_rate_max or 10)),
        max(1, int(settings.demo_ai_session_rate_window_sec or 60)),
    ):
        return False, "session-rate"

    cap = max(1, int(settings.demo_ai_max_messages or 30))
    if _SESSION_MESSAGES[session] >= cap:
        return False, "session-cap"

    day = _today()
    daily_cap = max(1, int(settings.demo_ai_daily_limit or 500))
    # Drop stale daily buckets so the dict cannot grow without bound.
    for old in [key for key in _DAILY if key != day]:
        _DAILY.pop(old, None)
    if _DAILY[day] >= daily_cap:
        return False, "daily-cap"

    _SESSION_MESSAGES[session] += 1
    _DAILY[day] += 1
    return True, ""


def fallback_reply_prefix() -> str:
    return FALLBACK_NOTE
