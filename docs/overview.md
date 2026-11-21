# FrontDesk AI overview

Web-only, self-hosted receptionist for clinics, salons and service businesses.

- `/`: premium responsive landing page, visitor feature explanation, actual supplied visitor-workflow screenshots, Live Demo link to `/admin/login`.
- `/chat`: customers ask questions and request appointments (length set in Admin → Settings, default 60 minutes). Knowledge answers and an OpenAI-compatible provider are configured by the production admin.
- `/admin`: business KPIs from real SQL records, seven-day activity, upcoming schedule and current inbox.
- `/admin/appointments`: search, workflow filters, status management.
- `/admin/conversations`: searchable inbox, complete transcript, guarded delete.
- `/admin/knowledge`: active FAQ management and categories.
- `/admin/settings`: hours, holidays, provider and private password management.

Admin remains a single role, with signed session and protected POST routes. Version 1.0.9 retains a separate public demo (`DEMO_MODE=true`) that never uses production admin credentials or a production database. Live AI replies are optional on that dedicated demo via `DEMO_ALLOW_AI=true` and a host-provided `AI_API_KEY`; see `SECURITY.md` and `DEMONSTRATION.md` for required constraints and limitations.

The page visitor may open `/chat` from navigation. Customer bookings use the configured appointment length with overlap/duplicate phone/hours/holiday checks. No mobile app or external messaging delivery is provided.

## Run and package deployment

For the complete GitHub/Render root, use Runtime Docker, Root Directory blank, `./Dockerfile`, context `.`, Docker Command blank. `render.yaml` is at archive root only. The source remains in `FrontDesk Project/`; the root builder explicitly copies its contents to `/app`, so `main:app` loads `/app/main.py`. There is no duplicate root lockfile or application copy.

From `FrontDesk Project/`: `uvicorn main:app --host 0.0.0.0 --port 10000`. Tables are created after model import. Production default is `sqlite:///./data/ai_receptionist.db`. Demo creates isolated scopes below `data/demo-*/`.

Optional fixed demo rows for a private installation are at ZIP-root `database/schema.sql` and `database/seed.sql` (no login in the SQL). The one-click public demo uses `app/demo.py` per signed browser session instead. The older images in `docs/screenshots/` are labelled v1.0.3 real product examples, not captures of the updated admin.
