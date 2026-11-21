"""Business/AI settings and admin password change."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.ai_service import get_appointment_minutes, get_setting, parse_appointment_minutes, set_ai_api_key, set_appointment_minutes, set_setting
from app.branding import MAX_LOGO_BYTES, LogoError, logo_url_for, remove_logo, save_logo
from app.auth import hash_password, is_weak_password, verify_password
from app.config import settings
from app.database import get_db
from app.demo_session import is_demo_session
from app.ownership import current_business_id
from app.security import block_demo_sensitive_action, ensure_password_hash, require_admin, verify_csrf
from app.web import business_context, render

# Every route in this module requires role=admin (router-level dependency);
# mutating handlers also declare it explicitly and verify CSRF.
router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/admin/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    demo = is_demo_session(request)
    if demo:
        # Never render env or stored provider values (including the API key).
        current = {
            "ai_base_url": "" if settings.demo_allow_ai else "Not available in demo",
            "ai_api_key_set": False,
            "ai_api_key": "",
            "ai_model": "" if settings.demo_allow_ai else "Local guided demo",
            "business_name": get_setting(db, "business_name", settings.business_name),
            "opening_hour": get_setting(db, "opening_hour", "9"),
            "closing_hour": get_setting(db, "closing_hour", "18"),
            "closed_days": get_setting(db, "closed_days", "sunday"),
            "holiday_dates": get_setting(db, "holiday_dates", ""),
            "appointment_minutes": get_appointment_minutes(db, current_business_id(request)),
        }
    else:
        current = {"ai_base_url": get_setting(db, "ai_base_url", settings.ai_base_url), "ai_api_key_set": bool(get_setting(db, "ai_api_key", "")), "ai_api_key": "", "ai_model": get_setting(db, "ai_model", settings.ai_model), "business_name": get_setting(db, "business_name", settings.business_name), "opening_hour": get_setting(db, "opening_hour", "9"), "closing_hour": get_setting(db, "closing_hour", "18"), "closed_days": get_setting(db, "closed_days", "sunday"), "holiday_dates": get_setting(db, "holiday_dates", ""), "appointment_minutes": get_appointment_minutes(db, current_business_id(request))}
    return render(request, "settings.html", business_context(db, request) | {"active_page": "settings", "current": current, "admin_name": get_setting(db, "admin_username", "admin"), "logo_url": logo_url_for(db, current_business_id(request))})


@router.post("/admin/settings")
async def save_settings(request: Request, ai_base_url: str = Form(""), ai_api_key: str = Form(""), ai_model: str = Form(""), business_name: str = Form(...), opening_hour: str = Form("9"), closing_hour: str = Form("18"), closed_days: str = Form("sunday"), holiday_dates: str = Form(""), appointment_minutes: str = Form(""), csrf_token: str = Form(""), db: Session = Depends(get_db), _: None = Depends(require_admin)):
    block_demo_sensitive_action(request)
    verify_csrf(request, csrf_token)
    try:
        opening, closing = int(opening_hour), int(closing_hour)
        if not 0 <= opening < closing <= 24:
            raise ValueError
        holidays = [d.strip() for d in holiday_dates.split(",") if d.strip()]
        for value in holidays:
            date.fromisoformat(value)
    except ValueError:
        return RedirectResponse("/admin/settings?error=schedule", status_code=303)
    business_id = current_business_id(request)
    minutes = get_appointment_minutes(db, business_id)
    if appointment_minutes.strip():  # field left out (older forms/API clients): keep current length
        try:
            minutes = parse_appointment_minutes(appointment_minutes)
        except ValueError:
            return RedirectResponse("/admin/settings?error=duration", status_code=303)
    if settings.demo_mode:
        # AI settings are host-env only in demo; never accept a form override.
        raise RuntimeError("demo AI settings are read-only")
    set_setting(db, "ai_base_url", ai_base_url.strip())
    if ai_api_key.strip():
        set_ai_api_key(db, ai_api_key.strip())
    set_setting(db, "ai_model", ai_model.strip())
    set_setting(db, "business_name", business_name.strip()[:200])
    set_setting(db, "opening_hour", str(opening))
    set_setting(db, "closing_hour", str(closing))
    set_setting(db, "closed_days", closed_days.strip().lower() or "sunday")
    set_setting(db, "holiday_dates", ",".join(holidays))
    set_appointment_minutes(db, business_id, minutes)  # only the signed-in admin's business
    return RedirectResponse("/admin/settings?saved=1", status_code=303)


@router.post("/admin/change-password")
async def change_password(request: Request, current_password: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...), csrf_token: str = Form(""), db: Session = Depends(get_db), _: None = Depends(require_admin)):
    block_demo_sensitive_action(request)
    verify_csrf(request, csrf_token)
    stored = ensure_password_hash(db)
    if not stored or not verify_password(current_password, stored):
        return RedirectResponse("/admin/settings?error=wrong_password", status_code=303)
    if new_password != confirm_password:
        return RedirectResponse("/admin/settings?error=mismatch", status_code=303)
    if len(new_password) < 8 or is_weak_password(new_password):
        return RedirectResponse("/admin/settings?error=too_short", status_code=303)
    set_setting(db, "admin_password", hash_password(new_password))
    return RedirectResponse("/admin/settings?password_changed=1", status_code=303)


@router.post("/admin/settings/logo")
async def upload_logo(request: Request, logo: UploadFile = File(...), csrf_token: str = Form(""), db: Session = Depends(get_db), _: None = Depends(require_admin)):
    """Replace the logo of the business owned by the logged-in admin."""
    block_demo_sensitive_action(request)  # demo sandboxes never write files
    verify_csrf(request, csrf_token)
    data = await logo.read(MAX_LOGO_BYTES + 1)
    try:
        save_logo(db, current_business_id(request), data)
    except LogoError as exc:
        return RedirectResponse(f"/admin/settings?error={exc.code}", status_code=303)
    return RedirectResponse("/admin/settings?logo_saved=1", status_code=303)


@router.post("/admin/settings/logo/remove")
async def delete_logo(request: Request, csrf_token: str = Form(""), db: Session = Depends(get_db), _: None = Depends(require_admin)):
    """Go back to the default 'F' mark for the logged-in admin's business."""
    block_demo_sensitive_action(request)
    verify_csrf(request, csrf_token)
    remove_logo(db, current_business_id(request))
    return RedirectResponse("/admin/settings?logo_removed=1", status_code=303)
