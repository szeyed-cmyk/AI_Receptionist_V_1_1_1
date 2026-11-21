"""Brand logo upload, validation, storage and lookup.

- Accepted: PNG, JPEG and WEBP only (SVG is refused: it can carry scripts).
- The real file content is checked (magic bytes + dimensions parsed from the
  image header), not the browser-supplied filename or content type.
- Max 1 MB and 2000 x 2000 pixels; the browser scales it down with CSS.
- Files live outside templates/static in ``<database folder>/uploads/<business_id>/``
  under a random name; the relative path is stored on ``Business.logo_path``.
- Served only through ``GET /brand/logo/{business_id}``, which reads the path
  from the database (never from the request) and checks it stays inside the
  uploads folder.
"""
from __future__ import annotations

import os
import secrets
import struct
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings

MAX_LOGO_BYTES = 1024 * 1024
MAX_LOGO_SIDE = 2000
CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}


class LogoError(ValueError):
    """Upload rejected; ``code`` is used in the settings page message."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def uploads_root() -> Path:
    """``uploads/`` next to the SQLite database (``./data/uploads`` by default)."""
    url = settings.database_url or ""
    if url.startswith("sqlite:///"):
        db_path = Path(url[len("sqlite:///"):])
        return (db_path.parent / "uploads").resolve()
    return Path("data/uploads").resolve()


def _png_size(data: bytes):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _jpeg_size(data: bytes):
    if data[:3] != b"\xff\xd8\xff":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + length
    return None


def _webp_size(data: bytes):
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if chunk == b"VP8L" and data[20:21] == b"\x2f":
        b = data[21:25]
        w = 1 + (((b[1] & 0x3F) << 8) | b[0])
        h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
        return w, h
    if chunk == b"VP8X":
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return w, h
    return None


def inspect_logo(data: bytes) -> str:
    """Return the file extension for valid logo bytes, else raise LogoError."""
    if not data:
        raise LogoError("logo_empty")
    if len(data) > MAX_LOGO_BYTES:
        raise LogoError("logo_too_big")
    for ext, probe in (("png", _png_size), ("jpg", _jpeg_size), ("webp", _webp_size)):
        size = probe(data)
        if size:
            w, h = size
            if not (0 < w <= MAX_LOGO_SIDE and 0 < h <= MAX_LOGO_SIDE):
                raise LogoError("logo_dimensions")
            return ext
    raise LogoError("logo_type")


def _resolve(relative: str | None) -> Path | None:
    if not relative:
        return None
    root = uploads_root()
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def save_logo(db: Session, business_id: int, data: bytes) -> str:
    """Validate and store a new logo for ``business_id``; deletes the old file."""
    from app.models import Business

    ext = inspect_logo(data)
    business = db.query(Business).filter(Business.id == business_id).first()
    if business is None:
        raise LogoError("logo_business")
    folder = uploads_root() / str(int(business_id))
    folder.mkdir(parents=True, exist_ok=True)
    name = f"logo-{secrets.token_hex(12)}.{ext}"
    tmp = folder / (name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, folder / name)
    old = _resolve(business.logo_path)
    business.logo_path = f"{int(business_id)}/{name}"
    db.commit()
    if old is not None:
        old.unlink(missing_ok=True)
    return business.logo_path


def remove_logo(db: Session, business_id: int) -> None:
    from app.models import Business

    business = db.query(Business).filter(Business.id == business_id).first()
    if business is None:
        return
    old = _resolve(business.logo_path)
    business.logo_path = None
    db.commit()
    if old is not None:
        old.unlink(missing_ok=True)


def logo_file(db: Session, business_id: int) -> tuple[Path, str] | None:
    """(path, content type) of a business logo, or None."""
    from app.models import Business

    business = db.query(Business).filter(Business.id == business_id).first()
    path = _resolve(business.logo_path if business else None)
    if path is None:
        return None
    return path, CONTENT_TYPES.get(path.suffix.lstrip("."), "application/octet-stream")


def logo_url_for(db: Session, business_id: int) -> str | None:
    from app.models import Business

    business = db.query(Business).filter(Business.id == business_id).first()
    if business is None or _resolve(business.logo_path) is None:
        return None
    version = Path(business.logo_path).stem.rsplit("-", 1)[-1][:8]
    return f"/brand/logo/{int(business_id)}?v={version}"


def brand_logo_url(request=None) -> str | None:
    """Jinja global: logo URL for the page being rendered, or None for the 'F' mark.

    Admin pages use the business in the signed session; public pages use the
    installation's public business. Demo mode always uses the default mark
    (uploads are disabled there).
    """
    if settings.demo_mode:
        return default_logo_url()
    from app.database import SessionLocal
    from app.ownership import public_business_id, session_business_id

    business_id = None
    if request is not None:
        try:
            business_id = session_business_id(request)
        except AssertionError:  # no session middleware on this request
            business_id = None
    with SessionLocal() as db:
        return logo_url_for(db, business_id or public_business_id(db)) or default_logo_url()


# Optional fixed logo shipped with the code (for example a public demo on Render,
# where uploads are disabled and the disk is not persistent). Put ONE of these
# files in static/brand/ and push it; it shows wherever no logo was uploaded.
DEFAULT_LOGO_NAMES = ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp")
STATIC_BRAND_DIR = Path(__file__).resolve().parent.parent / "static" / "brand"


def default_logo_url() -> str | None:
    for name in DEFAULT_LOGO_NAMES:
        path = STATIC_BRAND_DIR / name
        if path.is_file() and 0 < path.stat().st_size <= MAX_LOGO_BYTES:
            return f"/static/brand/{name}?v={int(path.stat().st_mtime)}"
    return None


DEFAULT_BRAND_NAME = "FrontDesk AI"


def public_brand() -> dict:
    """Name and appointment length shown on the public landing and chat pages.

    Production: the business name and appointment length from Admin -> Settings
    (fallbacks "FrontDesk AI" and 60). Demo mode keeps the fixed product name and
    the default length, without opening a reviewer sandbox for a page view.
    """
    if settings.demo_mode:
        return {"brand_name": DEFAULT_BRAND_NAME, "appointment_minutes": 60}
    from app.ai_service import get_appointment_minutes, get_setting
    from app.database import SessionLocal

    with SessionLocal() as db:
        name = (get_setting(db, "business_name", "") or "").strip()
        return {"brand_name": name[:200] or DEFAULT_BRAND_NAME, "appointment_minutes": get_appointment_minutes(db)}
