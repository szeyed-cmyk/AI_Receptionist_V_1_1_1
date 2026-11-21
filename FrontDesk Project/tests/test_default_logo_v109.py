"""Default logo from static/brand/ (used by the public demo)."""
import shutil
from pathlib import Path

import pytest

from app import branding

SRC = Path(__file__).resolve().parent.parent / "static" / "avatar.jpg"


@pytest.fixture
def default_logo(tmp_path, monkeypatch):
    monkeypatch.setattr(branding, "STATIC_BRAND_DIR", tmp_path)
    return tmp_path


def test_no_default_logo_returns_none(default_logo):
    assert branding.default_logo_url() is None


def test_default_logo_url_when_file_present(default_logo):
    shutil.copy(SRC, default_logo / "logo.jpg")
    assert branding.default_logo_url().startswith("/static/brand/logo.jpg?v=")


def test_demo_pages_show_default_logo(demo_client, tmp_path, monkeypatch):
    import app.branding as fresh  # demo_client re-imports the app package
    folder = tmp_path / "brand"
    folder.mkdir()
    monkeypatch.setattr(fresh, "STATIC_BRAND_DIR", folder)
    shutil.copy(SRC, folder / "logo.png")
    for url in ("/", "/admin/login", "/chat"):
        html = demo_client.get(url).text
        assert "/static/brand/logo.png?v=" in html, url
