"""v1.0.9: brand logo upload in Admin -> Settings, shown everywhere."""
from __future__ import annotations

import base64
import json
import re
import sqlite3
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET = "test-secret-key-for-pytest-only-not-production"


def _png(w=64, h=64) -> bytes:
    """Tiny valid PNG (solid colour) without Pillow."""
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x50\x64\xeb" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _csrf(client):
    page = client.get("/admin/settings")
    assert page.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def _upload(client, data, name="logo.png", ctype="image/png", token=None):
    token = token if token is not None else _csrf(client)
    return client.post("/admin/settings/logo", data={"csrf_token": token},
                       files={"logo": (name, data, ctype)}, follow_redirects=False)


def _logo_path(business_id=1):
    from app.database import SessionLocal
    from app.models import Business

    with SessionLocal() as db:
        return db.get(Business, business_id).logo_path


def test_upload_png_shows_everywhere(admin_client):
    r = _upload(admin_client, _png())
    assert r.status_code == 303 and r.headers["location"] == "/admin/settings?logo_saved=1"
    stored = _logo_path()
    assert re.fullmatch(r"1/logo-[0-9a-f]{24}\.png", stored)
    from app.branding import uploads_root
    assert (uploads_root() / stored).is_file()
    assert "templates" not in str(uploads_root()) and "static" not in str(uploads_root())

    settings_page = admin_client.get("/admin/settings").text
    assert 'data-testid="logo-preview"' in settings_page and "Remove logo / use default" in settings_page
    assert 'class="logo-mark logo-img' in settings_page            # admin sidebar
    assert '<link rel="icon" href="/brand/logo/1?v=' in settings_page  # favicon
    assert "square image works best; shown as a circle." in settings_page
    assert 'data-testid="logo-preview"' in settings_page
    assert "object-cover object-center" in settings_page
    assert "object-contain" not in settings_page
    assert "p-1.5" not in settings_page
    # Preview frame is a circle with no white pad when a logo is set
    assert re.search(r'rounded-full overflow-hidden shrink-0 aspect-square', settings_page)

    chat = admin_client.get("/chat").text
    assert re.search(r'id="messages" data-logo="/brand/logo/1\?v=[0-9a-f]{8}"', chat)
    assert 'data-testid="chat-header-avatar"' in chat and chat.count('src="/brand/logo/1?v=') >= 2  # nav + header avatar
    assert "bg-white p-1" not in chat
    assert "object-contain" not in chat
    assert "object-cover object-center" in chat
    assert "rounded-full overflow-hidden" in chat
    for path in ("/", "/admin/login"):
        page = admin_client.get(path).text
        assert 'class="logo-mark logo-img' in page, path
        assert "rounded-full overflow-hidden aspect-square shrink-0" in page, path
        assert 'object-cover object-center' in page, path

    img = admin_client.get("/brand/logo/1")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert img.content == _png() and "default-src 'none'" in img.headers["content-security-policy"]


def test_chat_js_renders_logo_avatar_for_assistant_messages():
    js = (ROOT / "static" / "chat.js").read_text()
    assert "messagesEl.dataset.logo" in js and "assistantAvatar()" in js
    assert "avatar.textContent = 'AI'" in js  # fallback badge
    assert "ai-avatar-logo" in js
    assert "object-cover object-center" in js
    assert "innerHTML" not in js


def test_uploaded_logo_css_is_a_circle_without_padding():
    """Custom logos are cropped into a circle; the default F/AI marks stay unchanged."""
    css = (ROOT / "static" / "app.css").read_text()
    # Default "F" mark is still the rounded square with the gradient.
    assert ".logo-mark{display:grid;place-items:center;width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,#6376f3,#7d67de);" in css
    # Default chat "AI" badge is still the rounded square.
    assert ".ai-avatar{width:30px;height:30px;flex:none;border-radius:9px;display:grid;place-items:center;overflow:hidden;background:#5064eb;" in css
    # Uploaded logo: circle, no white pad, cover-crop from the centre.
    assert ".logo-mark.logo-img{background:none;padding:0;overflow:hidden;border-radius:999px;aspect-ratio:1;flex-shrink:0;box-shadow:none}" in css
    assert "object-fit:cover;object-position:center" in css
    assert "background:#fff;padding:3px" not in css
    assert "object-fit:contain" not in css
    assert ".ai-avatar-logo{border-radius:999px;background:none;aspect-ratio:1;flex-shrink:0;padding:0}" in css


def test_new_logo_replaces_old_file(admin_client):
    from app.branding import uploads_root
    _upload(admin_client, _png())
    first = _logo_path()
    _upload(admin_client, _png(32, 32))
    second = _logo_path()
    assert first != second
    assert not (uploads_root() / first).exists() and (uploads_root() / second).is_file()


def test_svg_and_fake_images_are_rejected(admin_client):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert _upload(admin_client, svg, "logo.svg", "image/svg+xml").headers["location"].endswith("error=logo_type")
    # right name and content type, wrong content
    assert _upload(admin_client, b"GIF89a" + b"0" * 50, "logo.png", "image/png").headers["location"].endswith("error=logo_type")
    empty = _upload(admin_client, b"", "logo.png")
    assert empty.status_code == 422 or empty.headers["location"].endswith("error=logo_empty")
    assert _logo_path() is None
    assert "SVG is not accepted" in admin_client.get("/admin/settings?error=logo_type").text


def test_too_big_and_huge_dimensions_rejected(admin_client):
    big = _png() + b"\x00" * (1024 * 1024)
    assert _upload(admin_client, big).headers["location"].endswith("error=logo_too_big")
    huge = bytearray(_png())
    huge[16:24] = struct.pack(">II", 5000, 5000)
    assert _upload(admin_client, bytes(huge)).headers["location"].endswith("error=logo_dimensions")
    assert _logo_path() is None


def test_upload_requires_csrf_and_login(admin_client):
    r = _upload(admin_client, _png(), token="wrong")
    assert r.status_code == 403 and _logo_path() is None
    r = admin_client.post("/admin/settings/logo/remove", data={"csrf_token": "wrong"}, follow_redirects=False)
    assert r.status_code == 403
    admin_client.cookies.clear()  # anonymous visitor
    client = admin_client
    r = client.post("/admin/settings/logo", data={"csrf_token": "x"}, files={"logo": ("l.png", _png(), "image/png")}, follow_redirects=False)
    assert r.status_code in (303, 403) and r.headers.get("location", "/admin/login") == "/admin/login"
    assert _logo_path() is None


def _as_business(client, business_id):
    """Re-sign the current admin session cookie with another business_id (keeps the CSRF token)."""
    import itsdangerous

    signer = itsdangerous.TimestampSigner(SECRET)
    raw = client.cookies.get("frontdesk_session")
    payload = signer.unsign(raw.encode())
    session = json.loads(base64.b64decode(payload))
    session["business_id"] = business_id
    client.cookies.set("frontdesk_session", signer.sign(base64.b64encode(json.dumps(session).encode())).decode())
    return session["csrf_token"] if "csrf_token" in session else None


def test_other_business_cannot_change_or_remove_business_one_logo(admin_client):
    from app.database import SessionLocal
    from app.models import Business

    with SessionLocal() as db:
        db.add(Business(id=2, name="Other Clinic"))
        db.commit()
    _upload(admin_client, _png())
    own = _logo_path(1)
    token = _csrf(admin_client)
    _as_business(admin_client, 2)
    assert _upload(admin_client, _png(16, 16), token=token).status_code == 303
    admin_client.post("/admin/settings/logo/remove", data={"csrf_token": token}, follow_redirects=False)
    assert _logo_path(1) == own                       # business 1 untouched
    assert _logo_path(2) is None                      # removed its own (second) upload only
    assert 'data-testid="logo-preview"' not in admin_client.get("/admin/settings").text


def test_remove_goes_back_to_default_mark(admin_client):
    from app.branding import uploads_root
    _upload(admin_client, _png())
    stored = _logo_path()
    r = admin_client.post("/admin/settings/logo/remove", data={"csrf_token": _csrf(admin_client)}, follow_redirects=False)
    assert r.headers["location"] == "/admin/settings?logo_removed=1"
    assert _logo_path() is None and not (uploads_root() / stored).exists()
    chat = admin_client.get("/chat").text
    assert 'data-logo=""' in chat and ">F</span>" in chat and 'href="/static/favicon.svg"' in chat
    assert admin_client.get("/brand/logo/1").status_code == 404


def test_logo_route_ignores_tampered_paths(admin_client):
    from app.database import SessionLocal
    from app.models import Business

    with SessionLocal() as db:
        db.get(Business, 1).logo_path = "../../app/config.py"
        db.commit()
    assert admin_client.get("/brand/logo/1").status_code == 404
    assert 'data-logo=""' in admin_client.get("/chat").text


def test_demo_cannot_upload(demo_client):
    page = demo_client.get("/admin/login")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    assert demo_client.post("/admin/demo-login", data={"csrf_token": token}, follow_redirects=False).status_code == 303
    settings_page = demo_client.get("/admin/settings").text
    assert "Logo upload is disabled in the demo." in settings_page
    token = re.search(r'name="csrf_token" value="([^"]+)"', settings_page).group(1)
    r = demo_client.post("/admin/settings/logo", data={"csrf_token": token}, files={"logo": ("l.png", _png(), "image/png")}, follow_redirects=False)
    assert r.status_code == 403
    r = demo_client.post("/admin/settings/logo/remove", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code == 403
    assert demo_client.get("/brand/logo/1").status_code == 404
    assert 'data-logo=""' in demo_client.get("/chat").text


def test_v108_database_gets_logo_column(tmp_path):
    from sqlalchemy import create_engine
    from app.database import ensure_schema
    import app.models  # noqa: F401

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE businesses (id INTEGER PRIMARY KEY, name VARCHAR(160) NOT NULL, created_at DATETIME)")
    con.commit()
    con.close()
    ensure_schema(create_engine(f"sqlite:///{db}"))
    ensure_schema(create_engine(f"sqlite:///{db}"))  # idempotent
    cols = [r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(businesses)")]
    assert "logo_path" in cols


def test_uploads_kept_out_of_git_and_docker():
    repo = ROOT.parent
    assert "**/data/uploads/" in (repo / ".gitignore").read_text()
    assert "**/data/uploads/" in (repo / ".dockerignore").read_text()
