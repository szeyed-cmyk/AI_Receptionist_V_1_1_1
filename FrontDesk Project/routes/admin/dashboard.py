"""Admin dashboard metrics (queries live in app/dashboard_service.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.dashboard_service import dashboard_metrics
from app.database import get_db
from app.security import require_admin
from app.web import business_context, render

# Every route in this module requires role=admin (router-level dependency);
# mutating handlers also declare it explicitly and verify CSRF.
router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    """All metrics are scoped to the business owned by the logged-in admin."""
    return render(request, "admin.html", business_context(db, request) | {"active_page": "dashboard", **dashboard_metrics(db, request)})
