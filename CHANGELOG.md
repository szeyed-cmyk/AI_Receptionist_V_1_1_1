# CHANGELOG.md

## 1.0.9

### Live AI replies on the public demo (`DEMO_ALLOW_AI`)

- New opt-in environment flag `DEMO_ALLOW_AI=true`. With `DEMO_MODE=true`, this allows the host to set `AI_API_KEY` (and optionally `AI_BASE_URL` / `AI_MODEL`) so visitor `/chat` returns live AI replies. Without the flag, behaviour is unchanged: a set `AI_API_KEY` or `AI_BASE_URL` still prevents startup.
- `DATABASE_URL` (non-demo), `ADMIN_USERNAME`, `ADMIN_PASSWORD` and `SETUP_TOKEN` are still refused in demo mode, even when the flag is on. The startup error now mentions `DEMO_ALLOW_AI=true`.
- The key is read only from the environment. Demo Settings never shows or accepts AI configuration; reviewers cannot override it. The key is redacted from HTML, JavaScript and error text.
- Abuse protection for live demo AI: per-session and per-IP rate limits, `DEMO_AI_MAX_MESSAGES` (default 30), `DEMO_AI_DAILY_LIMIT` (default 500), max input length and `max_tokens`. When a cap is hit, chat falls back to the existing scripted demo replies with a short note. Bookings still write only to the per-session sandbox.
- The demo login page is unchanged (Enter Admin demo, fresh-sandbox green box, private account access form). Only when `DEMO_ALLOW_AI=true` does the green box say that AI replies are live (limited per session).
- Render / GitHub docs updated with the exact demo environment and the existing Docker settings (repository root, blank Root Directory, Python 3.12.7, one worker, `uvicorn main:app --host 0.0.0.0 --port $PORT`).

### Local setup on Windows, macOS and Linux

- HowToSetup.md section A now has complete local install, demo-mode, test and stop instructions for Windows (PowerShell and Command Prompt), macOS and Linux, including Python 3.12 install notes (python.org, Homebrew, apt/`python3.12-venv`, dnf), venv activation, `.env` and secret-key commands, and OS-specific troubleshooting (port in use, `py` / `python3` missing, PowerShell execution policy, macOS “Install Certificates.command”, permissions).
- Optional start helpers in `FrontDesk Project/`: `start.sh` (macOS/Linux), `start.ps1` (PowerShell) and `start.bat` (Command Prompt). They activate `.venv` or `venv` and run `python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}`.
- `python main.py` is documented as defaulting to port 8000 unless `PORT` is set in the process environment (it does not read `PORT` from `.env`). The recommended command remains uvicorn on port 10000.

### Circular brand logo

- An uploaded logo is shown as a perfect circle everywhere (admin sidebar, login, setup, landing header and footer, visitor chat top bar, chat header avatar, every assistant reply, and the Settings preview). Any image — wide, tall, square or transparent — is cropped with `object-cover` / `object-center` inside a fixed square (`rounded-full`, `overflow-hidden`, `aspect-square`, equal width and height, no padding). There is no white background, white padding, border or ring around the logo.
- The default “F” mark (admin/landing) and “AI” badge (chat) are unchanged when no logo is uploaded.
- Settings hint now reads “square image works best; shown as a circle.”
- Tests updated for the new classes and CSS; the default-mark rules are still asserted.

### Landing page (what FrontDesk AI does)

- New hero copy, approved from a preview first: badge “AI receptionist for service businesses”; headline “Answers questions. Books appointments. Never sleeps.” (accent colour on the last line); description of the 24/7 chat, answers from your business information, booking into open slots, and appointments landing in the admin dashboard; stats row “24/7”, “Instant booking”, “One dashboard”; line under the buttons “Try it as a visitor, then see the booking land in the admin.”
- Mobile headline size is 32px (desktop sizes unchanged) so each sentence stays on one line.
- Product, Features and Why FrontDesk sections rewritten so a business owner can see what the app actually does. Product explains the receptionist and a 3-step How it works (visitor asks → AI answers and books → you see it in the dashboard). Features is an eight-item grid of capabilities that exist in the code. Why FrontDesk covers after-hours enquiries, less phone/admin time, self-hosted one-time single-site licence, and branding plus the included demo. Copy is honest about limits: bookings stay inside opening hours; there is no website embed snippet and no email or text-message notifications. No testimonials, fake statistics, customer logos, or developer contact details.
- Tests updated: landing assertions match the new copy; the appointment-length test no longer expects the configured minutes on the hero (that figure was removed).

### Ownership check on appointment status (Vibe96 audit warning)

- `POST /admin/appointments/{appt_id}/status` no longer loads the appointment with `db.get(Appointment, appt_id)`. It now:
  1. verifies CSRF;
  2. calls `demo_blocks_mutation(request, "appointment", appt_id)` before any change (demo sessions may only change appointments they booked; seeded rows are read-only, 403);
  3. loads the row with `get_owned_or_404(db, Appointment, appt_id, request)`, i.e. `WHERE id = :id AND business_id = :business in the signed admin session`, answering 404 for other businesses' or missing appointments;
  4. validates the status (422 for anything other than confirmed/completed/cancelled).
- New appointments booked through the demo chat are registered with `demo_created(request, "appointment", ...)`, the same pattern used for FAQs and conversations.
- New `businesses` table and non-null `business_id` foreign key on `appointments`, `conversations` and `knowledge_items` (messages are owned through their conversation). `database/schema.sql` updated to match the models (checked by `test_schema_sql_matches_sqlalchemy_models`).
- Automatic, idempotent startup migration for existing databases: adds `business_id`, creates business 1 and assigns all existing rows to it. No manual SQL, no data loss.
- New `app/ownership.py` (`current_business_id`, `owned_query`, `owned_filter`, `get_owned_or_404`, `owned_messages_query`). The admin session now stores `business_id` (set at login, setup and demo login); `require_admin` rejects sessions without it, so admins sign in once after upgrading.
- Same scoping applied to every other id-based admin route: conversation detail/delete, FAQ edit form/update/delete, plus all lists, searches, dashboard metrics and the header "upcoming" badge. Public booking sets the owner on new conversations/appointments and checks duplicates/overlaps within that business only.
- Appointment list query/filter/count logic moved from the route handler into `app/appointments_service.py` (handler is now two lines); dashboard metrics likewise moved to `app/dashboard_service.py`.
- Fixed: in production, the FAQ **Edit** link and conversation **Delete** menu were hidden (the template helper only allowed demo-created rows). The template helper now allows all owned rows in production and only session-created rows in demo.
- Fixed: malformed `</span>` markup in the admin sidebar made "Open visitor chat" wrap onto several lines.
- New tests: `FrontDesk Project/tests/test_ownership_v109.py` (17 tests).

### Brand logo and chat page look

- **Admin → Settings → Brand logo:** upload a PNG/JPG/WEBP logo (max 1 MB, 2000 × 2000 px) with a live preview, or **Remove logo / use default**. SVG and files whose content is not a real PNG/JPEG/WEBP are refused. CSRF-protected, admin-only, scoped to the business in the signed session, disabled in demo mode.
- Stored outside templates in `uploads/<business id>/` next to the database with a random file name; path saved in the new `businesses.logo_path` column (added automatically to existing databases; `database/schema.sql` updated). Served by `GET /brand/logo/{business_id}` with a strict `Content-Security-Policy`; tampered paths outside the uploads folder are ignored.
- The logo replaces the "F" mark everywhere: admin sidebar, login, setup, landing header and footer, visitor chat top bar, chat header avatar and the avatar next to every assistant reply (`static/chat.js`, URL passed in a `data-logo` attribute), and the favicon. Falls back to "F" (and the "AI" badge in chat) when no logo is set.
- Visitor chat page (`/chat`) now uses the same dark navy background as the landing page (dot grid, violet and teal glows); the chat card stays white, full-height, with the message box always visible.
- `data/uploads/` excluded from git, Docker builds and the release zip.
- New tests: `FrontDesk Project/tests/test_brand_logo_v109.py` (12 tests).

### Appointment length in minutes

- **Admin → Settings → Business profile → Appointment length (minutes)**: 5–480, steps of 5, default 60. Validated on the server (0, 1000, decimals, text and non-multiples of 5 are refused and nothing is saved), CSRF-protected, admin-only, saved for the business in the signed session; read-only and blocked in the demo.
- Stored as `businesses.appointment_minutes` (added automatically to existing databases with 60; `database/schema.sql` updated). Each appointment keeps its own `duration_minutes` (empty values from old databases are set to 60), so changing the setting does not alter existing bookings.
- Everything that said "60 minutes" now uses the setting: booking end time and confirmation text, overlap check (each existing booking with its own length), new **closing-time check** (an appointment must end by the closing hour; the error tells the latest start time), AI system prompt, built-in replies (booking prompt, greeting, "How long is an appointment?"), the chat welcome message (`static/chat.js`, read from a `data-minutes` attribute), the note under the chat box, the Appointments "New booking length" figure, and the landing page figure/copy. Without an AI key, "How long is an appointment?" is still answered with the configured length. Demo slot seeding steps by the length.
- Fixed: `Appointment.end_time` fell back to 30 minutes when a duration was missing (now 60).
- Visitor chat page title, top bar and chat header show the **business name** from Settings (fallback "FrontDesk AI"; the demo keeps "FrontDesk AI").
- New tests: `FrontDesk Project/tests/test_appointment_length_v109.py` (24 tests).

### Documentation

- HowToSetup.md: quick-facts line; explicit **Required Python version: 3.12** section; new **Demo admin path** table (URL, no credentials, how to disable); rewritten **VPS deployment (Ubuntu 22.04/24.04)**: system user, venv, `.env`, systemd unit, nginx reverse proxy with forwarded headers, firewall (ufw), HTTPS with certbot, first admin, updating, backups, logs/troubleshooting; expanded **Branding (name, logo, colours)**; upgrade notes v1.0.8 → v1.0.9.
- README.md: "What you get", "Demo entry path", "Record ownership (v1.0.9)" and a full **License** section (single-site licence; own or one client project; no resale of the source). LICENSE-NOTE.md clarified accordingly.
- docs/SECURITY.md and docs/DEMONSTRATION.md updated for the ownership and demo rules.

### Dependencies and tooling

- `requirements.lock` regenerated from `requirements.txt` with the same tool and options (`uv pip compile --generate-hashes --universal --python-version 3.12`); only change: `annotated-doc` 0.0.5 → 0.0.6. `pip-audit`: no known vulnerabilities.
- Dev/test dependency: `pytest` 8.3.5 → 9.0.3 (PYSEC-2026-1845). Not used at runtime.
- Pyflakes/pycodestyle (`ruff --select E,F,W`) clean: unused imports and `== True` comparisons removed.

## 1.0.8

### Booking date fix ("10th November shows Sunday")

- Reproduced on v1.0.7 with today = Saturday 7 Nov 2026: `parse_datetime` ignored month names and ordinals and fell back to *tomorrow* (Sunday 8 Nov). The day number became the hour (`on 10th November at 5pm` → Sun 8 Nov 10:00), and `day after tomorrow` matched `tomorrow`. The demo chat therefore answered "We are closed on Sundays." for both phrases.
- New `app/datetime_parse.py: parse_booking_datetime` handles `10th November`, `10 November`, `November 10[, 2026]`, `10th of November`, ISO `2026-11-10`, unambiguous `13/11/2026`, `today` / `tomorrow` / `day after tomorrow`, weekday names, `am`/`pm`, `HH:MM` and `noon`. The weekday is always derived from the validated date.
- When a date has no year it uses the business's current year, or next year if that date has already passed. Leap years are validated.
- The parser never silently defaults. It asks the customer to clarify when the date is missing, the time is missing or has no AM/PM, the day/month order is ambiguous (`10/11`), the date is invalid, the time is in the past, or the stated weekday or relative day conflicts with the date.
- "Now" uses `BUSINESS_TIMEZONE` (default Asia/Dhaka), not server UTC.
- Booking confirmations state the full date (e.g. "Tuesday, 10 November 2026, 05:00 PM – 06:00 PM") and include `confirmed_date`.
- The AI prompt now states today's date and forbids guessing weekdays; the tool asks for `YYYY-MM-DD HH:MM`.
- The demo chat example no longer suggests "tomorrow", which is a closed Sunday whenever today is a Saturday.
- Demo chat accepts an introductory sentence with `name:` label and time-before-date fields (`I would like to book an appointment name:Ahmad,555-0199,Medicine doctor,5pm ,10th november`).
- New tests: `FrontDesk Project/tests/test_booking_dates_v108.py`. No dependency changes.

## 1.0.7

### "Invalid CSRF token" on Admin login - fix

- Reproduced: a sign-in form opened in a second tab, restored with the browser Back button (after entering or leaving the demo), or submitted after the session cookie was lost/expired/overwritten returned a raw `{"detail":"Invalid CSRF token"}` 403 page. `/admin` pages were also sent without `Cache-Control`, so browsers could re-show a stale token.
- `/admin*` HTML responses now send `Cache-Control: no-store, max-age=0` and `Pragma: no-cache`.
- A stale token on `/admin/login`, `/admin/demo-login` or `/admin/setup` now redirects (303) to a freshly rendered form with an "expired, nothing was submitted" message. It never signs anyone in and never auto-resubmits (no loop).
- Stale tokens on authenticated admin forms remain a 403: a short HTML "form expired" page for browsers (same-site link only), JSON for API clients. CSRF checking is unchanged; failures are logged by route only (no token/cookie values).
- Login page shows a correct message for `error=busy` (was "Invalid username or password").
- New tests: `FrontDesk Project/tests/test_csrf_recovery_v107.py`. No dependency changes.

## 1.0.6

### Vibe96 audit-warning release

- `.env.example` (root and `FrontDesk Project/`, identical): `SECRET_KEY=` blank with a local generation comment; `DATABASE_URL=` blank means the default SQLite path.
- Startup refuses blank/placeholder/short (<32) `SECRET_KEY` in every mode, including demo (`enforce_secret_key`).
- `DEMO_MODE=true` now **fails fast** if a non-demo `DATABASE_URL`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`, `SETUP_TOKEN`, `AI_BASE_URL` or `AI_API_KEY` is configured (previously silently ignored).
- `/admin/setup` POST rate-limited per client IP; token compare remains `secrets.compare_digest`.
- `routes/admin.py` split into `routes/admin/{dashboard,knowledge,settings,appointments,conversations}.py`; demo ownership helpers moved to `app/demo_session.py`; one shared template-context builder `app/web.py: render` replaces the two `_tpl` copies.
- Admin search escapes LIKE wildcards; edits/deletes use `db.get(Model, pk)`.
- Chat `max_length` reads `settings.chat_message_max_length`.
- Removed nested `FrontDesk Project/Dockerfile`, `.dockerignore`, `.gitignore`; the root files are canonical.
- Dependencies re-locked with hashes: uvicorn 0.54.0, sqlalchemy 2.0.57 (latest 2.0.x), pydantic 2.14.3, pydantic-settings 2.16.2, python-multipart 0.0.33, python-dotenv 1.2.4; fastapi 0.162.0, jinja2 3.1.6, cryptography 50.0.2 already latest. `pip-audit`: no known vulnerabilities.
- Booking parser accepts explicit `YYYY-MM-DD` dates (fixes a weekend-dependent test).
- Docs: Python 3.12.x and SQLite 3.35+ prerequisites; ordered Compose steps; `docs/AUDIT-RESOLUTION-v1.0.6.md`.
- New tests: `FrontDesk Project/tests/test_audit_v106.py`.

## 1.0.5

### Root-first GitHub → Render release

- Added a primary root `Dockerfile` with explicit JSON COPY arguments. It installs `FrontDesk Project/requirements.lock`, then copies only the nested application contents to `/app`; the image has `/app/main.py`, absolute templates/static paths and the `uvicorn main:app` CMD on `${PORT:-10000}`.
- Added root-first `render.yaml`: Docker runtime, `rootDir: .`, `dockerfilePath: ./Dockerfile`, `dockerContext: .`, `/health`, one instance and no native build/start override. `SECRET_KEY generateValue: true` uses supported Blueprint semantics; `sync:false` fields have no provided secret values.
- Removed the contradictory nested Python Blueprint. Retained the nested Dockerfile only for an explicitly selected standalone source context; Compose and GitHub→Render use the primary root builder and its root `.dockerignore`.
- Root Compose reads root `.env`, maps host `${PORT:-10000}` to container port 10000 and retains `FrontDesk Project/data:/app/data`. Matching `.env.example` files now default to port 10000. No root Python source or second lockfile is added.
- Added root/nested secret, DB, journal, demo, Git, virtualenv and cache ignore protection; root-first GitHub/Render guide, Windows `py` examples, demo credential/AI omissions, one-worker quota/storage limits and upgrade guidance.
- Added root deployment regressions for nested source quoting, flattened main/template/static loading, real Docker CMD startup on default and explicit ports, official Moby ignore matching, temporary git ignore behavior and YAML/archive structure. Optional Go helper is vendored Apache-2.0 source, compiled offline in a temp directory; no compiled executable is packaged.
- Product UI, templates, static/assets, routes, CSRF/auth guards, bcrypt hashing, Fernet key handling and isolated demo semantics remain functionally unchanged. Only version identification and related test expectations changed in app Python.

### Verification notes (local only)

- Original application suite after complete version-expectation update: **38 passed**. Aggregate app/deployment discovery: **49 passed, 2 skipped** in the initial staged clean-tree run (archive validation runs after packaging; a Docker image build does not happen without an engine). The root ZIP-path regression from release source: **1 passed**.
- Fresh-child-process flattened import/template/static checks and exact Linux root Docker `sh -c`/`main:app` startup over local HTTP passed. Both the default `${PORT:-10000}` fallback with unset `PORT` and an alternate `PORT` were tested without `FRONTDESK_TESTING`. `.env.example` settings remain independent of Compose's explicit root environment.
- The nested lockfile is byte-identical to v1.0.4. `pip-audit -r FrontDesk Project/requirements.lock` reported **No known vulnerabilities found**. Root Blueprint passed the retained current Render JSON-schema snapshot. Compose/Blueprint also have direct static YAML regression checks.
- There is no Docker/Podman Engine on this box. No image pull, actual Docker/Compose container engine build/start, Render service update, submission or Marketplace approval is claimed. The isolated filesystem and host Uvicorn results are not a Docker base-image build or production audit. Run `docker build -f Dockerfile .` and service staging checks in your own environment.
- Deprecated SQLAlchemy `datetime.utcnow` and pinned Starlette TestClient warnings are retained in test output; they are not failing assertions. The landing dashboard screenshot is the v1.0.4 browser-QA capture, preserved unchanged; no new v1.0.5 visual/browser approval claim.

## 1.0.4

### Vibe96 marketplace UI/resubmission work

- New `/` product landing page: responsive hero, Live Demo button to `/admin/login`, visitor-chat CTA, real supplied product screenshots, benefits, features and self-hosted positioning. No invented testimonials, figures or contacts. Public chat moved to `/chat`.
- Rebuilt admin UI into one cohesive responsive system with accessible navigation, business header, safe mobile sidebar, local Tailwind build and custom CSS, common tables/forms/statuses. No runtime external CDN/tracking/font dependency.
- Dashboard backed by actual SQL metrics: today/upcoming/total bookings, conversations, messages, FAQ total, seven-day conversation activity, calculated conversation-to-booking conversion, current bookings/inbox.
- Appointments management adds search, status filters, explicit allowed-status saves and counts. Conversations add searchable inbox and message/visitor context; original protected deletion retained.
- Knowledge base enables adding, editing, activation/draft state, search and category. Settings adds controlled hours/holiday validation and an 8-character password minimum.
- Improved logged-out admin login and SETUP_TOKEN setup presentation. Auth/CSRF/session protections preserved.

### Isolated review demo

- Optional `DEMO_MODE` only. One-click **Admin demo** on login represents the application's only real role, admin; no invented user role.
- Discards production DSN, AI credentials and admin bootstrap/secrets for the demo engine. Independent signed demo cookie and secret namespace prevent replay of production cookies.
- New signed session contains an opaque scope; isolated fictional fixtures under `data/demo-<seed>/` mean each review session has its own data, including anonymous demo chat. Does not open production `DATABASE_URL`.
- FAQ creation/editing/deletion and chat deletion restricted to this signed session's ownership; seed/other reviewer records are protected. Fictional appointment status updates enabled with CSRF and allowlist.
- Demo account, provider, schedule and setup operations blocked server-side even for admin+valid CSRF. Local deterministic FAQ/booking prevents external AI/network charges/secrets; this is a guided demonstration, not a claim of external AI capability.
- Demo capacity guard defaults 200 scopes per worker and is documented as non-distributed. Demo SQLite files are disposable and need operator cleanup; Render ephemeral FS resets are expected for the review installation only.

### Delivery maintenance

- Retained ZIP-root `.env.example` for archive layout and Docker Compose; added byte-identical `FrontDesk Project/.env.example` for adjacent local-app setup. Updated Linux/macOS, Windows PowerShell, VPS, Compose and Render instructions to distinguish working directories and private `.env` destinations. No application behavior changed.

- Landing showcase now uses the actual v1.0.4 admin demo dashboard (`static/admin-demo-dashboard.png`) supplied after browser QA. Removed the stale cleaning-price/45-minute example from the landing; updated alt, caption and provenance. No application behavior changed.

- Security headers added; static asset caching; all assets served locally with Tailwind licence notice.
- Updated `README.md`, `HowToSetup.md`, `CLAUDE.md`, `.env.example`, `render.yaml`, `docker-compose.yml`, `docs/overview.md`, `docs/DEMONSTRATION.md`, `docs/SECURITY.md` (roles, route guards, demo tradeoffs, VPS/Docker/Render env and upgrades).
- Archive screenshot folder gets provenance readme: older v1.0.3 product images are not presented as new admin captures.
- Removed generated DB/caches from release ZIP; preserved original v1.0.3 source/ZIP separately. No user contact info in code/docs.

### Verification (v1.0.4)

```
$ python -m pytest -q
......................................
38 passed

$ pip-audit -r requirements.lock
No known vulnerabilities found
```

All 22 earlier tests plus 16 new tests (landing/local assets, real metrics/management, knowledge edit, appointment validation, settings validation, one-click auth, production DSN/credential isolation, privilege protections, local network-free demo, reviewer ownership, demo booking, cross-mode stale cookies, capacity limit and unauthenticated guards). One subprocess/local uvicorn smoke check verifies landing/login/health and does not create a configured production test DSN. Browser QA passed the landing CTAs, one-click admin demo, management pages and opening-hours FAQ without console errors; the dashboard screenshot was replaced accordingly. No unrelated functionality was changed by later documentation/template updates. Automated HTML/test-client checks cannot verify pixel layout or JavaScript click behavior.

Warnings are deprecation notices (SQLAlchemy `datetime.utcnow` and the pinned Starlette TestClient adapter) with no failing assertions. No live deployment, submission, upload, or external AI call was performed.

## 1.0.3

- Public `POST /chat` binds conversations to a signed visitor session (`visitor_token`); foreign / guessed `conversation_id` values return 403
- Chat per-IP rate limit (`request.client.host`) and 2000-character message cap; documented as intentional public endpoint in `docs/SECURITY.md` and README
- `/admin/setup` requires `SETUP_TOKEN`; disabled when an admin exists or `ADMIN_PASSWORD` bootstrap is set
- Login rate limit uses `request.client.host`; documented uvicorn `--proxy-headers --forwarded-allow-ips`
- Removed plaintext password fallback; bcrypt only (passlib removed)
- `SECRET_KEY` placeholder/empty refuses startup outside `FRONTDESK_TESTING=1`
- AI API key encrypted at rest (Fernet derived from `SECRET_KEY`)
- Schema/models: FK cascades, indexes on FK / `updated_at` / `(customer_phone, appointment_time)`; paginated conversations & appointments with `selectinload`; deletes return 404 when missing
- Shared CSRF / rate-limit / template helpers; `app/templating.py`, `app/chat_service.py`, `app/crypto.py`
- Dockerfile installs from `requirements.lock` with `--require-hashes`; added `.dockerignore`
- docker-compose uses root `.env`, forwards `AI_*` / `PORT` / `SETUP_TOKEN`; no business-default fallbacks baked in
- HowToSetup: Python 3.12+, ordered steps, VPS + Docker + Windows, demo admin creation, SECRET_KEY generation
- pip-audit recorded below; dependency pins refreshed (bcrypt, cryptography; passlib dropped)

### Vulnerability audit (1.0.3)

```
$ pip-audit -r requirements.lock
No known vulnerabilities found
```

Pinned runtime set includes fastapi 0.162.0, uvicorn 0.40.0, cryptography 50.0.2,
python-multipart 0.0.31, python-dotenv 1.2.2, bcrypt 4.3.0 (passlib removed).

## 1.0.2

- Reorganized for Vibe96 archive layout: docs and `database/` at ZIP root; all application code inside `FrontDesk Project/`
- Split routes into `routes/public.py`, `routes/auth.py`, `routes/admin.py` with `require_admin` in `app/security.py`
- Admin router declares `dependencies=[Depends(require_admin)]`; every mutating admin handler also lists `Depends(require_admin)`
- Session stores `user` + `role=admin`; role also recorded in settings as `admin_role`
- Added `docs/SECURITY.md` route/guard table and richer `database/seed.sql` demo data
- HowToSetup covers Ubuntu VPS (systemd + nginx), Docker Compose, and Windows (`py`)
- Added mutating-route authorization test; pinned lockfile refreshed

## 1.0.1

- Replaced forgeable `admin=true` cookie with signed Starlette session
- CSRF on admin POST forms; login rate limit; constant-time username compare
- Warns when `SECRET_KEY` is still the default placeholder
- Business hours: Mon–Sat 09:00–18:00, closed Sunday; holidays and hours from settings
- Booking rejects overlap, closed days, holidays, outside hours, and duplicate phone
- Added pytest suite

## 1.0.0

- Web chat, knowledge base, appointment booking, admin dashboard
