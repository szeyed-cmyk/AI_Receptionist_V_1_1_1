"""Shared Jinja2Templates instance (absolute path, no working-directory dependency)."""
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _brand_logo_url(request=None):
    from app.branding import brand_logo_url

    return brand_logo_url(request)


templates.env.globals["brand_logo_url"] = _brand_logo_url
