# FrontDesk AI

**v1.0.9 · Self-hosted AI receptionist for clinics, salons and service businesses**

FrontDesk AI combines a modern responsive landing page, visitor chat, appointments with a length you set (default 60 minutes), and an authenticated business dashboard. Admin, bookings, conversations, FAQs, settings, secure one-click isolated demo, and tests are included.

- **Landing:** `/`
- **Visitor chat:** `/chat`
- **Admin workspace:** `/admin/login` → `/admin`
- **Health:** `/health` reports version `1.0.9` and avoids exposing secrets.

## What you get

- **Visitor chat (`/chat`)** that answers from your own FAQ list and books appointments of the length you set in Settings (5–480 minutes, default 60) inside your opening hours (each must end by closing time), rejecting closed days, holidays, overlapping slots and duplicate phone numbers.
- **Admin dashboard (`/admin`)** with today's and upcoming bookings, conversations, messages, FAQ count, seven-day activity and booking conversion.
- **Appointments, Conversations, Knowledge and Settings** pages with search, filters, status changes (confirmed / completed / cancelled) and FAQ editing.
- **Any OpenAI-compatible AI provider** (OpenAI, Groq, OpenRouter, Together, local Ollama), configured in Admin → Settings; the API key is encrypted at rest.
- **Security built in:** signed admin sessions, CSRF on every form, bcrypt passwords, login/setup/chat rate limits, and (v1.0.9) every admin record lookup scoped to the owning business.
- **Safe public demo mode** with a private fictional sandbox per reviewer.
- **Deploy anywhere:** local (Linux/macOS/Windows `py`), Docker Compose, Render (root `render.yaml`) or an Ubuntu VPS with nginx + HTTPS (full guide in [HowToSetup.md](HowToSetup.md#e-vps-deployment-ubuntu-2204--2404--nginx--https)).
- **Tests included:** 130+ automated tests (`python -m pytest -q`).

## Demo entry path

| | |
|---|---|
| Turn demo on | `DEMO_MODE=true` and a fresh `SECRET_KEY`. Leave `DATABASE_URL`, `ADMIN_*` and `SETUP_TOKEN` unset (the app refuses to start otherwise). For live AI replies on that public demo also set `DEMO_ALLOW_AI=true` and provide `AI_API_KEY` (optionally `AI_BASE_URL` / `AI_MODEL`) in the host environment |
| Demo admin URL | **`/admin/login` → click "Enter Admin demo"** (also reached from the **Live demo** button on `/`) |
| Credentials | **None needed.** The button (`POST /admin/demo-login`, CSRF-protected) opens `/admin` in a private sandbox with fictional data |
| Visitor demo | `/chat`, e.g. `Ahmad, 555-0199, dental checkup, next Monday at 3pm` |
| Turn demo off (production) | `DEMO_MODE=false` (default) and restart. `/admin/demo-login` returns 404, the demo button disappears, and only real admin accounts can sign in |

In the demo a reviewer can add/edit their own FAQs, start conversations and change the status of appointments they booked in the chat during that session. Seeded records, settings, AI keys and passwords are read-only. Details: [HowToSetup.md, section C](HowToSetup.md#demo-admin-path-how-reviewers-enter-the-demo) and [docs/DEMONSTRATION.md](docs/DEMONSTRATION.md).

## Record ownership (v1.0.9)

Appointments, conversations (with their messages) and FAQs belong to a business (`business_id`). The signed admin session stores the business the admin owns, and every admin list, search, count, view, edit, status change and delete is filtered by it through `app/ownership.py` (`get_owned_or_404`, `owned_query`). A record of another business answers **404**, the same as a missing one. Existing databases are migrated automatically on startup (all old rows are assigned to business 1). See [docs/SECURITY.md](docs/SECURITY.md).

## Root-first GitHub → Render deployment

**Deploy the full unpacked package from its root using Docker.** The codebase remains only in `FrontDesk Project/` per the packaged structure; root orchestration files are configuration, not a second application copy. Read **[GITHUB-RENDER.md](GITHUB-RENDER.md)** for detailed GitHub upload and Render settings.

| Required Render setting | Exact value |
|---|---|
| Runtime / Language | **Docker** |
| Root Directory | **blank** (use repository root) |
| Dockerfile Path | **./Dockerfile** |
| Docker Build Context | **.** (repository root) |
| Docker Command | **blank**, use root Dockerfile CMD |
| Build Command | blank / not used for Docker |
| Start Command override | blank / not used for Docker |
| Health Check Path | **/health** |
| Instance count | **1** while using SQLite / process-local demo capacity |

The root `render.yaml` is the one canonical Blueprint. Its `rootDir: .` explicitly matches repository root; Docker builds extract the correct source and entrypoint below. No stale nested Blueprint is shipped.

### Why the original root-docker failure is fixed

The root Dockerfile explicitly resolves nested requirements then flattens **only** the source directory:

```dockerfile
COPY ["FrontDesk Project/requirements.lock", "/app/requirements.lock"]
RUN pip install --no-cache-dir --require-hashes -r /app/requirements.lock
COPY ["FrontDesk Project/", "/app/"]
```

The trailing slash on the source copies the directory **contents**; JSON quoting preserves the space in `FrontDesk Project`. `/app/main.py`, `/app/app`, `/app/routes`, `/app/templates`, `/app/static` and `/app/requirements.lock` result; `/app/FrontDesk Project/main.py` is not needed. CMD starts `uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}` in the Linux image shell, following Render's default optional `PORT` behavior. There is no root `main.py` and no root `requirements.lock` copy to maintain.

Upload the **contents** of the extracted ZIP into the GitHub repository root—not the ZIP itself or another enclosing `FrontDesk_AI-*` directory. Do not copy the nested lockfile or any app file to GitHub root; v1.0.6 ships exactly one Dockerfile (at the root). If your repository has manually duplicated root lockfile or stale root Docker files from a workaround, replace/remove those conflicting tracked deployment files as part of your own repository update. Do not delete user data or production databases; review and secure any sensitive files in repository history.

For manual Render Docker services, configure these fields yourself. Alternatively use the root `render.yaml` Blueprint; omit native build/start commands. `/app/requirements.lock` comes from `FrontDesk Project/requirements.lock`; no container-wide root `COPY . .` is used. Image includes application runtime only, not docs or root `.env`.

### One Docker build (v1.0.6)

Compose, Render and manual builds all use `docker build -f Dockerfile .` from the complete root. Root `.dockerignore` filters the build context and the nested contents are copied into a flat `/app` inside the image. v1.0.6 removed the optional nested `Dockerfile`/`.dockerignore` so there is exactly one canonical build configuration.

Successful `main:app` import in a simulated flattened `/app` runtime uses both source app routes and absolute static/template references underneath it. Root tests materialize the image layout, ignore files and the real Uvicorn process—but **actual image build/startup requires Docker/BuildKit** and is unverified if an engine isn't available locally.

## Archive / repository layout

```text
. (upload all of these CONTENTS, not ZIP nor enclosing parent)
├── Dockerfile
├── .dockerignore
├── .gitignore
├── render.yaml                       # root-first Docker, canonical
├── docker-compose.yml                # root .env; root Docker context/file
├── .env.example                      # no secrets, same as nested example
├── README.md
├── HowToSetup.md
├── GITHUB-RENDER.md
├── CLAUDE.md
├── CHANGELOG.md
├── LICENSE-NOTE.md
├── database/
│   ├── schema.sql
│   └── seed.sql
├── docs/                             # security, demo and overview
├── tests/                            # root deployment regression tests
└── FrontDesk Project/
    ├── main.py
    ├── requirements.lock
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── runtime.txt
    ├── .env.example                  # identical placeholder root copy
    ├── app/
    ├── routes/
    ├── templates/
    ├── static/
    ├── tests/
    └── data/                         # private runtime DB generation only
```

No `main.py`, `requirements.lock`, `app/`, `templates/` or `static/` is duplicated at repository root. No real `.env`, SQLite DB, demo sandbox, `.git`, venv or cache belongs in the ZIP.

## Requirements

- **Python 3.12.x** (Docker image: `python:3.12.7-slim`) and **SQLite 3.35 or newer** (bundled with Python's `sqlite3`).
- `SECRET_KEY` is mandatory (>= 32 characters, generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`); the app refuses to start without it, in every mode.
- Audit-warning resolutions for v1.0.6 are documented in [docs/AUDIT-RESOLUTION-v1.0.6.md](docs/AUDIT-RESOLUTION-v1.0.6.md).

## Environment configuration

Two byte-identical placeholder `.env.example` files are intentional: the root copy is read by Docker Compose (`cp .env.example .env` at the root), the `FrontDesk Project/` copy sits next to `main.py` for local runs, because the app reads `.env` from its working directory. `SECRET_KEY=` is blank in both. Neither contains usable secrets and neither substitutes for a real private environment variable configuration. **Keep both examples synchronized whenever editing a placeholder variable.** Compare `cmp .env.example "FrontDesk Project/.env.example"` at archive root (Linux/macOS) or the two `(Get-FileHash ...).Hash` results (PowerShell). Root `.gitignore` and root `.dockerignore` exclude actual `.env` files, key material, DB/journal files, sandboxes, interpreters and caches.

| Workflow | Working directory | Configuration |
|---|---|---|
| Local Linux/macOS/Windows/VPS | `FrontDesk Project/` | Same-directory `.env` created manually from adjacent `.env.example` |
| Docker Compose at archive root | Root with `docker-compose.yml` | **Root `.env`** from root `.env.example` |
| GitHub → Render Docker | Full extracted root → repository root | Render Environment settings; no committed/private `.env` |
| Standalone nested Docker build | Entire `FrontDesk Project` context | Explicit container environment values; example only for reference |

`app/config.py` specifies relative `env_file=".env"` resolved against runtime **working** directory; app folders are not searched upward for archive-root `.env`. Local/VPS starts from nested source folder. Compose explicit `env_file: .env` and root variable interpolation are not the local app dotenv search and still get root secrets. Docker root build copies nested app contents only, so no private root env ends up in static code, templating or static media.

### Local Linux / macOS

After extracting the archive, from its root:

```bash
cd "FrontDesk Project"
python3.12 -m venv venv
source venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"  # paste as SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(24))"  # paste as SETUP_TOKEN
mkdir -p data
python -m app.init_db
python -m uvicorn main:app --host 0.0.0.0 --port 10000
```

Edit `.env` **before initialization** to substitute private `SECRET_KEY`, and `SETUP_TOKEN` for browser setup (or private `ADMIN_USERNAME`, `ADMIN_PASSWORD` alternative). Visitor URLs: localhost:10000/, /admin/login, /chat. `ADMIN_PASSWORD` is hashed when first successful login bootstraps it. Keep `HTTPS_ONLY=true` behind HTTPS proxy. Set local `HTTPS_ONLY=false` otherwise.

### Windows PowerShell (`py` + venv)

From archive root (after `Set-Location` to extracted root):

```powershell
Set-Location ".\FrontDesk Project"
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -c "import sys; assert sys.version_info >= (3, 12)"
python -m pip install --require-hashes -r requirements.lock
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"  # paste as SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(24))"  # paste as SETUP_TOKEN
New-Item -ItemType Directory -Force data | Out-Null
python -m app.init_db
python -m uvicorn main:app --host 0.0.0.0 --port 10000
```

`py -3.12` creates the required Python 3.12 venv; subsequent installed and runtime commands intentionally use activated venv's `python`, avoiding dependency writes to the system interpreter. Edit `.env` before init. Don't substitute `source` or Command Prompt's activate command into PowerShell.

### Docker Compose

At the extracted root, create root `.env` using the root example and replace the mandatory `SECRET_KEY`. Supply `SETUP_TOKEN` or private `ADMIN_*` to initialize a private installation.

```bash
cp .env.example .env
docker compose up --build
```

PowerShell: `py -3.12 -c 'import secrets; print(secrets.token_urlsafe(48))'`; then `Copy-Item .env.example .env`; edit it privately and run same docker compose command. By default listen at `http://localhost:10000`, mapping host `${PORT:-10000}` to internal 10000. If host `PORT` is set to 8080 browse to 8080. Root runtime data maps `/app/data` to nested `FrontDesk Project/data`; one nested copy in the package. There is no need to create project `.env` simultaneously with this Compose setup. Actual Compose uses root `context: .`, `dockerfile: Dockerfile`.

### Render secrets and demo-opt-in guidance

**Default production** is `DEMO_MODE=false`, `HTTPS_ONLY=true`. Root `render.yaml` defines `SECRET_KEY` with `generateValue: true`. The **published Render Blueprint specification supports generating a random base64-encoded 256-bit value** when the variable is not already set. Render preserves existing secret values on subsequent Blueprint syncs. No guarantee of secret rotation after configuration unless managed by operator.

Optional Blueprint secret `sync: false` entries prompt for input during **initial creation only**. On updates, newly added or changed `sync:false` values are ignored; enter them via Render Environment manually. A **manual Docker service** can't assume automatic Blueprint secret generation; generate and enter your own fresh private `SECRET_KEY` using Render's credentials controls. Required production choices remain private `SETUP_TOKEN` or a private `ADMIN_USERNAME` / `ADMIN_PASSWORD` bootstrap.

**Dedicated one-click public review** must be a **separate clean Render service** with: `DEMO_MODE=true`, `DEMO_SEED=review-v1`, `DEMO_MAX_SESSIONS=200`, `HTTPS_ONLY=true`, and a fresh `SECRET_KEY` generated by Render or manually. Leave `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SETUP_TOKEN` and `DATABASE_URL` unset. To show live AI replies in `/chat` (and keep the one-click admin demo), also set `DEMO_ALLOW_AI=true` and add `AI_API_KEY` as a secret, plus `AI_BASE_URL` (defaults to `https://api.openai.com/v1` if blank) and `AI_MODEL` (defaults to `gpt-4o-mini` if blank). The key is read only from the environment; reviewers cannot view or change it in Settings. Without `DEMO_ALLOW_AI=true` the app still refuses to start if `AI_API_KEY` or `AI_BASE_URL` is set. Never point this service at a real customer database.

Production *must* remain `DEMO_MODE=false` and use persistent storage, such as a disk mounted `/app/data` or owner-managed persistent DB appropriate for the app. No disk, database or deployment is provisioned by this archive. Free ephemeral SQLite sample/sandboxes reset as expected. Demo has per-signed cookie scoped storage under `data/demo-<seed>/`, scripted FAQ/booking by default (or live host AI when `DEMO_ALLOW_AI=true`, with per-session and daily caps), and server-required CSRF/role/ownership restrictions. An admin demo may change the status of appointments it booked itself and manage only its own new FAQs/chat. It cannot delete or alter seed/other reviewer records or sensitive settings. Default cap 200 scopes is per-worker, not distributed; sandboxes not auto-purged. Operator chooses external reset/cleanup for long-lived public demo.

## Included behavior preserved from v1.0.4

- Actual SQL-backed KPI dashboard: today/upcoming schedules, conversations, messages, FAQs, seven-day conversation activity, calculated booking conversion.
- Search/filter appointments; confirmed/completed/cancelled statuses only.
- Conversation listing/detail and CSRF-protected ownership guard.
- FAQ add/edit/enable/disable/filter/delete; safe hours/holidays provider settings and password length.
- Signed sessions, sole real role `admin`, role checks at router and mutation level; CSRF, login/session rate limiting, secure initial bootstrap honoring placeholders only in tests.
- bcrypt password hashes, Fernet encryption for configured API key and invalid-key error controls; no plaintext fallback or credentials in UI source.
- Modern navigation/dashboard/landing and actual old visitor example with current v1.0.4 admin dashboard capture captioned as fictional data. Historical v1.0.3 docs screenshots explicitly remain historical.
- All assets are local, including local Tailwind vendor license. Environment provider can be any OpenAI-compatible URL/auth stored in admin settings (no provider network in demo paths).

## Run tests and dependency audit

From archive root with a local virtualenv and requirements-dev installed:

```bash
python -m pip install --upgrade pip
python -m pip install -r "FrontDesk Project/requirements-dev.txt"
python -m pytest -q
python -m pip-audit -r "FrontDesk Project/requirements.lock"
```

`pytest -q "FrontDesk Project/tests"` selects original application suite only. Root `tests/` includes root build/ignore/file layout/Blueprint/Compose/flattened-app startup regression checks. Root Dockerfile always consumes nested lock. Install root-test YAML support with `python -m pip install -r tests/requirements.txt` if `python -m pytest` reports missing PyYAML. The original application dev requirements only add pytest/pip-audit and already have the app's transitive YAML via `pip-audit`; root tests do not change runtime dependencies.

An optional `tests/docker_matcher` source helper calls upstream Moby pattern matching to verify real Docker ignore semantics. It builds offline if Go is installed with bundled licensed source, skipping that assertion otherwise; the application never needs Go. Real `.gitignore` behavior is tested only against synthetic files in a newly initialized temporary repo. Exact Docker Linux CMD is launched on temporary local HTTP endpoints with a generated secret (not test-bypass) on default port 10000 if free plus an alternate port. Temporary DBs go under pytest temp storage, never the packaged data directory.

No Docker Engine image build/container startup or Render deployment was available/run locally. Flattened tests and isolated YAML schema validation do not substitute for those checks. `docker build -f Dockerfile .` from the archive root in your own Docker environment before publishing. No Vibe96 or any Marketplace audit approval is promised.

HowToSetup describes local/Windows/Docker/VPS detailed commands and update from 1.0.4. Only external runtime AI provider chat makes network requests when manually configured production settings. No deployment submission automatically runs with packaged test.

## License

FrontDesk AI is sold under a **single-site commercial licence** (full text: [LICENSE-NOTE.md](LICENSE-NOTE.md)).

**You may:**
- use the full source code for **one business / one brand**, either your own or **one client project** you build for;
- modify, rebrand and extend the code for that business;
- keep staging, test and backup copies for that same business.

**You may not:**
- resell, sublicense, share or redistribute the source code, as-is or modified, as a template, script, theme or competing product;
- use one purchase for several unrelated businesses or clients (buy one licence per business).

Third-party libraries keep their own licences (see `requirements.lock`; Tailwind licence in `FrontDesk Project/static/vendor/LICENSE-tailwind.txt`). The software is provided as-is, without warranty. No personal contact information or embedded secret credentials are included. The Docker base image is `python:3.12.7-slim`; locked Python packages are installed with `--require-hashes`.

Developer: Syed Abue Tayeb Al-Zeyed
