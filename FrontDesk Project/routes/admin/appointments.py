"""Appointment list, search and status updates.

Ownership: every query is scoped to the business owned by the logged-in admin
(``app.ownership``); records are never loaded by id alone. Query logic lives in
``app.appointments_service`` so handlers stay short.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.appointments_service import APPOINTMENT_STATUSES, appointments_page
from app.database import get_db
from app.demo_session import demo_blocks_mutation
from app.models import Appointment
from app.ownership import get_owned_or_404
from app.security import require_admin, verify_csrf
from app.web import business_context, render

# Every route in this module requires role=admin (router-level dependency);
# mutating handlers also declare it explicitly and verify CSRF.
router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/admin/appointments", response_class=HTMLResponse)
async def appointments_list(request: Request, db: Session = Depends(get_db), status: str = "", q: str = ""):
    context = appointments_page(db, request, status, q)
    return render(request, "appointments.html", business_context(db, request) | {"active_page": "appointments", **context})


@router.post("/admin/appointments/{appt_id}/status")
async def update_appointment_status(appt_id: int, request: Request, status: str = Form(...), csrf_token: str = Form(""), db: Session = Depends(get_db), _: None = Depends(require_admin)):
    verify_csrf(request, csrf_token)
    # Demo sandboxes: only appointments booked in THIS signed session may change.
    if demo_blocks_mutation(request, "appointment", appt_id):
        raise HTTPException(status_code=403, detail="You can only change appointments you booked in this demo session")
    # Ownership check: WHERE id = :id AND business_id = :admin's business.
    # Another business's appointment answers 404, exactly like a missing one.
    appt = get_owned_or_404(db, Appointment, appt_id, request, detail="Appointment not found")
    if status not in APPOINTMENT_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported appointment status")
    appt.status = status
    db.commit()
    return RedirectResponse("/admin/appointments?updated=1", status_code=303)
