# HowToSetup.md

**Quick facts:** Python **3.12** required · app folder `FrontDesk Project/` · start `uvicorn main:app` · health check `/health` · admin login `/admin/login` · **demo admin path: `/admin/login` → "Enter Admin demo"** (only when `DEMO_MODE=true`, see section C) · VPS + nginx guide: section E · branding: section G.

Step-by-step install for v1.0.9. Application code remains in `FrontDesk Project/`; documentation, SQL and deployment configuration stay at the archive root. Read root-first `GITHUB-RENDER.md` when preparing GitHub or Render.

## Archive layout and environment files

The archive root holds deployment files and root documentation. **Python code, source templates, static assets and application tests remain inside the single `FrontDesk Project/` source directory.** It is shipped nested; only the Docker build puts its contents directly in `/app`.

```text
.
├── Dockerfile                       # primary root-first builder
├── .dockerignore
├── .gitignore
├── render.yaml                      # canonical root Docker Blueprint
├── docker-compose.yml               # root .env, root Docker context/file
├── .env.example                     # no private secret values
├── README.md
├── HowToSetup.md
├── GITHUB-RENDER.md
├── CLAUDE.md
├── CHANGELOG.md
├── LICENSE-NOTE.md
├── database/schema.sql
├── database/seed.sql
├── docs/
└── FrontDesk Project/
    ├── .env.example                 # byte-identical to root template
    ├── .env                         # create locally; never in the archive
    ├── main.py
    ├── start.sh / start.ps1 / start.bat   # optional local starters (section A)
    ├── requirements.lock            # sole lock, copied from nested path
    ├── app/, routes/, templates/, static/, tests/   # the ONLY runtime source tree
    └── data/                        # runtime-created local database path
```

### Working directory / configuration matrix

| Workflow | Working directory | Real private config |
|---|---|---|
| Local Python / Linux / Windows | `FrontDesk Project/` | Adjacent project `.env` |
| Ubuntu VPS/systemd | `/opt/frontdesk/FrontDesk Project` | `/opt/frontdesk/FrontDesk Project/.env` |
| Docker Compose | Complete archive root | Archive-root `.env` |
| GitHub → Render Docker | Repository root holding all extracted contents | Render Environment; no committed `.env` |

Local code loads `env_file=".env"` relative to its process working directory, not its source module and not an automatic parent-directory search. Run local application and initialization from `FrontDesk Project/` whose `main.py` is present. `cp ../.env.example .env` from that directory is equivalent to `cp .env.example .env`; both example copies are synchronized.

Compose is different: root `env_file: .env` and local interpolation (`${SECRET_KEY}`, `${PORT:-10000}`) both source archive-root `.env`. `${PORT:-10000}` controls the **host** port while `PORT=10000` is explicitly given to the container process. Its `context: .` / `dockerfile: Dockerfile` selects the single root Dockerfile (v1.0.6 removed the competing nested Dockerfile/.dockerignore). Compose reads root `.env`; a plain local run reads adjacent project `.env`. Do not assume either searches both locations or has secret values from the other workflow by default.

Render gets exactly the **entire archive root** at repository root; leave Root Directory blank and set Build Context `.`. A root `.env` is neither needed nor safe in GitHub. Blueprint or Environment settings provide runtime variables. `FrontDesk Project/render.yaml` is intentionally absent, so it cannot conflict with root-first Render discovery.

### Lockfile & two-image filesystem layout

The root Dockerfile first installs `COPY ["FrontDesk Project/requirements.lock", "/app/requirements.lock"]`; then the space-quoted nested **contents** go into `/app` with:

```dockerfile
COPY ["FrontDesk Project/", "/app/"]
```

The result has `/app/main.py`, `/app/app`, `/app/routes`, `/app/templates`, `/app/static`, and `/app/requirements.lock`; no `/app/FrontDesk Project` directory or root Python duplicates are needed. No archive root docs, root env, DB, `.git`, user venvs or unnecessary caches are brought into `/app`, because the builder copies only that nested folder after the context ignores private/environment/runtime files.

```bash
# The only Docker builder (Compose, Render and manual builds), with root .dockerignore:
docker build -f Dockerfile .
```

The container runs Uvicorn `main:app` on `${PORT:-10000}` in their Linux shell. Do not append project subdirectory to the primary `dockerContext` or change Root Directory for Render; that prevents correct sources from entering the image. Input contexts and resulting app placement are covered by regression tests.

Root `.dockerignore` excludes private `.env` under directories (except `.env.example` templates), keys/certificates, credentials, DB files/journals, sandbox data, Git metadata, virtual environments, caches/test outputs. Root `.gitignore` similarly prevents accidental Git tracking of private data. **Neither pattern rules replace keeping sensitive content outside a package or scanning a repository before disclosure.**

### Keep both examples synchronized

```bash
# Linux/macOS, archive root
cp .env.example "FrontDesk Project/.env.example"
cmp .env.example "FrontDesk Project/.env.example"
```

```powershell
# PowerShell, archive root
Copy-Item .env.example ".\FrontDesk Project\.env.example"
(Get-FileHash .env.example).Hash -eq (Get-FileHash ".\FrontDesk Project\.env.example").Hash  # True
```

```bat
:: Command Prompt, archive root
copy .env.example "FrontDesk Project\.env.example"
fc /b .env.example "FrontDesk Project\.env.example"
```

DEMO_MODE remains `false` in the example. For any changed public variables change *the two examples together only with placeholders*, never a filled environment file.


## Requirements (prerequisites)

### Required Python version: 3.12

- **Python 3.12.x is required** (the Docker image uses `python:3.12.7-slim`; `FrontDesk Project/runtime.txt` says `python-3.12`). Python 3.11 or older will not work. Python 3.13 also passed the test suite in v1.0.9 checks, but 3.12 is the supported target.
- **SQLite 3.35 or newer** (the version bundled with Python's `sqlite3` module). Foreign keys are enabled on every connection by the app.
- pip (installs with `--require-hashes -r requirements.lock`)
- Optional: Docker + Docker Compose, nginx, systemd (VPS)
- Optional: `sqlite3` CLI if you want to load `database/seed.sql` by hand

Check the interpreter and SQLite after install:

| OS | Check Python 3.12 | Check SQLite |
|---|---|---|
| Windows | `py -3.12 --version` | `py -3.12 -c "import sqlite3; print(sqlite3.sqlite_version)"` |
| macOS | `python3.12 --version` | `python3.12 -c "import sqlite3; print(sqlite3.sqlite_version)"` |
| Linux | `python3.12 --version` | `python3.12 -c "import sqlite3; print(sqlite3.sqlite_version)"` |

### Install Python 3.12

#### Windows

1. Download the **Python 3.12** Windows installer from [python.org/downloads/windows](https://www.python.org/downloads/windows/) (64-bit).
2. Run the installer. Tick **Add python.exe to PATH** and keep the **py launcher** enabled (it is on by default).
3. Close and reopen PowerShell or Command Prompt, then run `py -0p` to list installed versions and `py -3.12 --version` to confirm 3.12.
4. If `py` is not found, see [Common local troubleshooting](#common-local-troubleshooting).

#### macOS

Pick one:

- **Official installer:** download Python 3.12 from [python.org/downloads/macos](https://www.python.org/downloads/macos/). After installation, run **Install Certificates.command** (in `/Applications/Python 3.12/`). Without that step, `pip` may fail with an SSL certificate error. Then use `/usr/local/bin/python3.12` (or `python3.12` if it is on your `PATH`).
- **Homebrew:** install [Homebrew](https://brew.sh) if needed, then:

```bash
brew install python@3.12
$(brew --prefix python@3.12)/bin/python3.12 --version
```

Homebrew may not put `python3.12` on your `PATH` until you follow the caveats it prints (`brew info python@3.12`). Using the `$(brew --prefix python@3.12)/bin/python3.12` path is reliable.

#### Linux

- **Ubuntu 24.04 / Debian with Python 3.12 already in the repos:**

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

The `python3.12-venv` package is required; without it, `python3.12 -m venv .venv` fails with `ensurepip is not available`.

- **Ubuntu 22.04** (ships Python 3.10): add the deadsnakes PPA first, then install 3.12, the same way as in [section E](#e1-server-packages-and-python-312):

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

- **Fedora / RHEL-like (dnf):**

```bash
sudo dnf install -y python3.12
python3.12 -m venv --help   # venv is included in the python3.12 package on Fedora
```

Confirm `python3.12 --version` prints 3.12.x.

---

## A. Local install (Windows, macOS, Linux)

Local runs always use the **`FrontDesk Project/`** folder as the working directory. The private config file is `FrontDesk Project/.env` (Compose is different: it reads the archive-root `.env` — see the matrix above). The documented local URL is **http://localhost:10000** (`/chat` for the visitor chat, `/admin/login` for admin, `/health` for a health check).

Install dependencies from **`requirements.lock`** with hash checking (`python -m pip install --require-hashes -r requirements.lock`). Do not skip `--require-hashes` unless a locked package is genuinely unavailable on your platform; troubleshoot the interpreter first.

This guide uses a virtual environment named **`.venv`**. An older copy of this file used `venv`; that name still works, and the start scripts accept either.

After setup you can start the app with the commands in each OS section, or with the helpers in `FrontDesk Project/`:

| OS | Start script (from `FrontDesk Project/`) |
|---|---|
| Linux / macOS | `./start.sh` |
| Windows PowerShell | `.\start.ps1` |
| Windows Command Prompt | `start.bat` |

The recommended start command (what those scripts run) is:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 10000
```

`python main.py` also works, but it reads `PORT` from the **process environment only**, and defaults to **8000** if `PORT` is unset. It does not pick `PORT` up from `.env`. Prefer `python -m uvicorn ... --port 10000` (or `./start.sh` / `.\start.ps1` / `start.bat`, which default to 10000 and honour a `PORT` you have already exported/`set`).

Leave the virtual environment activated and stay in `FrontDesk Project/` while the server is running.

### Command overview

| Step | Windows PowerShell | Windows Command Prompt | macOS | Linux |
|---|---|---|---|---|
| Enter the app folder | `Set-Location ".\FrontDesk Project"` | `cd "FrontDesk Project"` | `cd "FrontDesk Project"` | `cd "FrontDesk Project"` |
| Create venv | `py -3.12 -m venv .venv` | `py -3.12 -m venv .venv` | `python3.12 -m venv .venv` | `python3.12 -m venv .venv` |
| Activate | `.\.venv\Scripts\Activate.ps1` | `.venv\Scripts\activate.bat` | `source .venv/bin/activate` | `source .venv/bin/activate` |
| Copy env file | `Copy-Item .env.example .env` | `copy .env.example .env` | `cp .env.example .env` | `cp .env.example .env` |
| Generate a secret | `py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"` | same `py -3.12 -c ...` | `python3.12 -c "import secrets; print(secrets.token_urlsafe(48))"` | `python3.12 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| Install packages | `python -m pip install --require-hashes -r requirements.lock` | same | same (after activate, the command is `python`) | same |
| Start | `python -m uvicorn main:app --host 0.0.0.0 --port 10000` | same | same | same |
| Or start script | `.\start.ps1` | `start.bat` | `./start.sh` | `./start.sh` |
| Stop / leave venv | `Ctrl+C`, then `deactivate` | `Ctrl+C`, then `deactivate` | `Ctrl+C`, then `deactivate` | `Ctrl+C`, then `deactivate` |

Use the generated secret as `SECRET_KEY` in `.env` (at least 32 characters). Generate a second value for `SETUP_TOKEN` unless you set `ADMIN_USERNAME` and `ADMIN_PASSWORD` instead (see [section C](#c-first-admin-login--demo-account)).

### 1. Linux

1. Unzip the archive, then enter the application folder:

```bash
cd "FrontDesk Project"
```

2. Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

If `python3.12 -m venv` reports that `ensurepip` is not available, install `python3.12-venv` (see [Install Python 3.12](#linux) above). After activation, the `python` command is this venv, not the system interpreter.

3. Confirm you are in the right folder (`ls main.py requirements.lock .env.example` should all exist), then install the pinned dependencies:

```bash
python -m pip install --require-hashes -r requirements.lock
```

If a locked package is unavailable on your platform, troubleshoot the interpreter first rather than silently skipping hash verification. Do not replace pinned security-sensitive versions without testing.

4. Create the private environment file and generate secrets:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste as SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(24))"   # paste as SETUP_TOKEN
```

This creates `FrontDesk Project/.env`. The ZIP must contain only `.env.example`, not a filled `.env`. `cp ../.env.example .env` is also correct because both example copies are identical. `../.env.example` is **not** loaded automatically by a local app run here. Edit `.env` (for example `nano .env`) and paste the two values. Optionally set `ADMIN_USERNAME` / `ADMIN_PASSWORD` to skip the setup form (when set, `/admin/setup` is disabled). Keep `HTTPS_ONLY=false` for `http://localhost`. Leave `DEMO_MODE=false` for a normal install.

5. Create the data directory and initialize the database (optional — the app also creates tables on first start). `.env` must already contain `SECRET_KEY` before this command, because importing the app checks it:

```bash
mkdir -p data
python -m app.init_db
```

Optional demo data (fictional clinic):

```bash
sqlite3 data/ai_receptionist.db < ../database/schema.sql
sqlite3 data/ai_receptionist.db < ../database/seed.sql
```

6. Start the server from this `FrontDesk Project` directory:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 10000
# or: ./start.sh
```

Do not `cd` to the ZIP root before starting locally. Behind a reverse proxy, add trusted forwarded headers:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 10000 \
  --proxy-headers --forwarded-allow-ips='127.0.0.1'
```

7. Open http://localhost:10000

### 2. macOS

The steps match Linux. Use `python3.12` (or `$(brew --prefix python@3.12)/bin/python3.12` if Homebrew did not link the name).

1. Unzip the archive and enter the application folder:

```bash
cd "FrontDesk Project"
```

2. Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

3. Install pinned dependencies:

```bash
python -m pip install --require-hashes -r requirements.lock
```

If `pip` fails with an SSL certificate error and you used the python.org installer, run `/Applications/Python 3.12/Install Certificates.command` and try again.

4. Create `.env` and generate secrets:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste as SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(24))"   # paste as SETUP_TOKEN
```

Edit `.env` (for example `nano .env` or `open -e .env`) and paste the values, as in the Linux steps.

5. Initialize the database if you want to (optional):

```bash
mkdir -p data
python -m app.init_db
```

6. Start the server:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 10000
# or: ./start.sh
```

If `./start.sh` is not executable (for example after unzipping on some systems), run `chmod +x start.sh` once.

7. Open http://localhost:10000

### 3. Windows (PowerShell and Command Prompt)

Install Python 3.12 so that the **`py` launcher** works (`py -3.12 --version`). After the venv is activated, use `python` (the venv interpreter), not `py`, for pip, secrets already generated inside the venv, uvicorn and pytest. `py -3.12` is still used to *create* the venv.

Confirm you are in `FrontDesk Project` before creating `.env`: in PowerShell, `Test-Path .env.example`, `Test-Path requirements.lock` and `Test-Path main.py` should each return `$True`. In cmd, `dir .env.example`, `dir requirements.lock` and `dir main.py` should list those files.

#### PowerShell

Run **Windows PowerShell** (or PowerShell 7). From the unpacked archive root:

```powershell
py -0p
Set-Location ".\FrontDesk Project"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked (`...Activate.ps1 cannot be loaded because running scripts is disabled`), run this once for your user account, then retry `.\.venv\Scripts\Activate.ps1`:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Or start the app later without changing the policy: `powershell -ExecutionPolicy Bypass -File .\start.ps1`.

Do not use `source`, and do not use Command Prompt's `activate.bat`, inside PowerShell. In each new PowerShell window, activate `.venv` again before running the app.

```powershell
python -m pip install --require-hashes -r requirements.lock
Copy-Item .env.example .env
py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"  # paste as SECRET_KEY
py -3.12 -c "import secrets; print(secrets.token_urlsafe(24))"  # paste as SETUP_TOKEN
```

This is `FrontDesk Project\.env`, not `..\.env` (the latter is for Compose only). `Copy-Item ..\.env.example .env` is equivalent because the two example files are identical. Edit the file (`notepad .env`) and paste the generated values. Leave `ADMIN_*` blank to use browser setup, or set them to bootstrap the first admin. Keep `HTTPS_ONLY=false` for `http://localhost`. Leave `DEMO_MODE=false` for a normal install.

```powershell
python -c "import sys; assert sys.version_info >= (3, 12)"
New-Item -ItemType Directory -Force data | Out-Null
python -m app.init_db
python -m uvicorn main:app --host 0.0.0.0 --port 10000
# or: .\start.ps1
```

The `data` folder is created only on your machine; no database is packaged. Open `http://localhost:10000`.

#### Command Prompt (`cmd.exe`)

```bat
cd "FrontDesk Project"
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --require-hashes -r requirements.lock
copy .env.example .env
py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
py -3.12 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Edit `.env` with `notepad .env` and paste the two values as `SECRET_KEY` and `SETUP_TOKEN`. Then:

```bat
mkdir data
python -m app.init_db
python -m uvicorn main:app --host 0.0.0.0 --port 10000
# or: start.bat
```

In cmd, do **not** put quotes around values in `set` (for example `set DEMO_MODE=true`, not `set DEMO_MODE="true"`). Quoted values keep the quote characters and can break configuration.

### Demo mode (local review)

Demo mode is a dedicated review instance with fictional, per-session sandbox data. The app **refuses to start** if `DEMO_MODE=true` is combined with a production `DATABASE_URL`, `SETUP_TOKEN`, `ADMIN_USERNAME` or `ADMIN_PASSWORD`. `AI_API_KEY` and `AI_BASE_URL` are also refused unless you set `DEMO_ALLOW_AI=true` (the key then comes only from the environment; reviewers cannot see or change it). Without live AI, use a demo-only `.env` that contains only `SECRET_KEY`, `HTTPS_ONLY`, `DEMO_MODE`, `DEMO_SEED` and optionally `DEMO_MAX_SESSIONS`. Do not point this at a real customer database. Read `../docs/DEMONSTRATION.md` first. Full reviewer path: [section C](#demo-admin-path-how-reviewers-enter-the-demo).

From `FrontDesk Project/`, with the venv activated:

**Linux / macOS**

```bash
export DEMO_MODE=true
export DEMO_SEED=local-review
export HTTPS_ONLY=false
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
# Leave DATABASE_URL, SETUP_TOKEN, ADMIN_USERNAME and ADMIN_PASSWORD unset.
# For live AI replies also set DEMO_ALLOW_AI=true and AI_API_KEY (plus AI_BASE_URL / AI_MODEL).
# If an existing .env sets ADMIN_*/SETUP_TOKEN/a production DATABASE_URL, demo mode will not start — use a clean .env instead.
# Without DEMO_ALLOW_AI=true, a set AI_API_KEY or AI_BASE_URL also prevents startup.
python -m uvicorn main:app --host 0.0.0.0 --port 10000
```

**Windows PowerShell**

```powershell
$env:DEMO_MODE = "true"
$env:DEMO_SEED = "local-review"
$env:HTTPS_ONLY = "false"
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
# The parentheses are required so the generated key is captured.
# "1" or "yes" also enable DEMO_MODE; this project’s docs use "true".
python -m uvicorn main:app --host 0.0.0.0 --port 10000
```

These variables apply only to this PowerShell window. Clear them before switching back to a normal install:

```powershell
Remove-Item Env:DEMO_MODE, Env:DEMO_SEED, Env:HTTPS_ONLY, Env:SECRET_KEY -ErrorAction SilentlyContinue
```

**Windows Command Prompt**

```bat
set DEMO_MODE=true
set DEMO_SEED=local-review
set HTTPS_ONLY=false
for /f %i in ('python -c "import secrets; print(secrets.token_urlsafe(48))"') do set SECRET_KEY=%i
python -m uvicorn main:app --host 0.0.0.0 --port 10000
```

In a `.bat` file write `%%i` instead of `%i`. Then open `http://localhost:10000/admin/login` and click **Enter Admin demo**. Never set `DEMO_MODE=true` on production data.

### Running the test suite

Install the runtime lock first, then the dev extras, with the same venv activated.

**From `FrontDesk Project/` (application tests):**

```bash
# Linux / macOS (venv activated)
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

```powershell
# Windows PowerShell (venv activated)
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

```bat
:: Windows Command Prompt (venv activated)
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

**Full suite from the archive root** (application tests plus root deployment tests). Keep the same venv activated, then:

```bash
# Linux / macOS
cd ..
python -m pip install -r tests/requirements.txt
python -m pytest -q "FrontDesk Project/tests" tests
```

```powershell
# Windows PowerShell
Set-Location ..
python -m pip install -r tests/requirements.txt
python -m pytest -q "FrontDesk Project/tests" tests
```

`tests/requirements.txt` adds PyYAML for a subset of the root tests. One root test is skipped when Docker is not available. The test run uses a temporary database; it does not need your real `.env`.

### Stopping the app and leaving the virtual environment

1. In the terminal where uvicorn is running, press **Ctrl+C** and wait for it to exit.
2. Leave the virtual environment: `deactivate` (PowerShell, cmd, macOS and Linux).
3. The `.venv` folder stays on disk; in a new terminal, activate it again before starting the app.

To use a different port: set `PORT` in the environment (`export PORT=8080`, `$env:PORT = "8080"`, or `set PORT=8080`) and pass the same value to uvicorn or the start script. Browse to that port.

### Common local troubleshooting

**Port 10000 is already in use**

- Linux: `ss -ltnp | grep 10000` or `lsof -iTCP:10000 -sTCP:LISTEN`
- macOS: `lsof -iTCP:10000 -sTCP:LISTEN`
- Windows (cmd or PowerShell): `netstat -ano | findstr :10000`

Stop the other process, or start on another port (see above). On Windows, the last column is the PID; `taskkill /PID <pid> /F` stops it. On macOS/Linux, `kill <pid>` (or `kill -9 <pid>` if it does not exit).

**`py` is not found (Windows)**

The Python installer did not add the launcher, or the terminal was not reopened. Re-run the 3.12 installer from [python.org](https://www.python.org/downloads/windows/), enable the **py launcher** and **Add python.exe to PATH**, then open a new window. Check with `py -0p`. Do not try to use the Microsoft Store stub if it is not 3.12.

**`python3` or `python3.12` is not found (macOS / Linux)**

Install 3.12 using the steps in [Install Python 3.12](#install-python-312). On macOS with Homebrew, call `$(brew --prefix python@3.12)/bin/python3.12` if `python3.12` is not on your `PATH`. On Linux, `python3` alone may be 3.10 or 3.11 — always use `python3.12` to create the venv. After activation, `python` (no suffix) is correct.

**PowerShell: `Activate.ps1` cannot be loaded**

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Or bypass the policy for a single start: `powershell -ExecutionPolicy Bypass -File .\start.ps1`. Do not set the execution policy to `Unrestricted` for all users unless you understand the risk.

**macOS SSL / `CERTIFICATE_VERIFY_FAILED` when running pip**

If you installed Python from python.org, run:

```bash
open "/Applications/Python 3.12/Install Certificates.command"
```

Then retry `python -m pip install --require-hashes -r requirements.lock`. Homebrew Python usually does not need this.

**`ensurepip is not available` / `python3.12 -m venv` fails (Linux)**

Install the venv package for that exact version: `sudo apt install -y python3.12-venv`.

**Permission errors during `pip install` or venv creation**

Do not use `sudo` with `pip` or `venv` for this project. Create `.venv` inside `FrontDesk Project/` as your own user. If a previous attempt was run with `sudo`, the folder may be owned by root — fix the owner (`sudo chown -R "$USER" .venv`) or delete `.venv` and create it again without `sudo`. On Windows, “Run as administrator” is usually the wrong fix; use a writable copy of the project in your user directory (for example under `Documents`), not a protected location.

**The app exits immediately about `SECRET_KEY`**

`.env` is missing, still has a blank `SECRET_KEY`, or you started from the archive root instead of `FrontDesk Project/`. The app looks for `.env` in the **current working directory**. Generate a key and put it in `FrontDesk Project/.env`.

**`DEMO_MODE=true` refuses to start**

A production value is also set (in the environment or in `.env`): `DATABASE_URL`, `SETUP_TOKEN`, `ADMIN_USERNAME` or `ADMIN_PASSWORD`. `AI_API_KEY` / `AI_BASE_URL` also block startup unless `DEMO_ALLOW_AI=true`. Use a dedicated demo `.env` or unset the conflicting variables. See above and section C.

**`python main.py` opened port 8000, not 10000**

That entry point defaults to 8000 unless `PORT` is set in the process environment. Use `python -m uvicorn main:app --host 0.0.0.0 --port 10000` or the start scripts.

## B. Windows PowerShell local install (`py`)

Windows local setup, including PowerShell **and** Command Prompt, is in [section A, Windows](#3-windows-powershell-and-command-prompt). That section uses `py -3.12 -m venv .venv` and `.\.venv\Scripts\Activate.ps1` (plus `activate.bat` for cmd). An earlier revision of this file used a folder named `venv` instead of `.venv`; if you already created `venv`, keep using it (`.\venv\Scripts\Activate.ps1` or `venv\Scripts\activate.bat`). The start scripts accept either name.

## C. First admin login / demo account

### Option 1 — browser setup (requires SETUP_TOKEN)

1. Visit http://localhost:10000/admin/setup
2. Enter username, password (min 8 characters; avoid weak passwords), and the `SETUP_TOKEN` from `.env`.
3. You are redirected to the dashboard.

### Option 2 — environment bootstrap

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `FrontDesk Project/.env` before starting a local/VPS installation, or in archive-root `.env` for supplied Compose. `/admin/setup` is disabled. Log in at `/admin/login`; the password is hashed into the database on first successful login.

### Demo admin path (how reviewers enter the demo)

| Item | Value |
|---|---|
| Switch | `DEMO_MODE=true` plus a fresh `SECRET_KEY`. For live AI replies also set `DEMO_ALLOW_AI=true` and `AI_API_KEY` (host environment only) |
| Entry URL | `https://<your-demo-host>/admin/login` (also linked from the landing page **Live Demo** button at `/`) |
| How to enter | Click **Enter Admin demo**. It sends a CSRF-protected `POST /admin/demo-login` and opens `/admin` |
| Demo credentials | **None.** No username/password is needed or accepted in demo mode; each click creates a private sandbox with fictional data |
| Visitor side | `/chat` (try: `Ahmad, 555-0199, dental checkup, next Monday at 3pm`) |
| What reviewers can change | FAQs they add, conversations they start, and the status of appointments they book in the chat during that session. Seeded rows, settings, keys and passwords are read-only |
| Disable for production | Set `DEMO_MODE=false` (the default) and restart. `/admin/demo-login` then returns 404 and the **Enter Admin demo** button disappears; only real admin logins work |

Local try-out, from `FrontDesk Project/` with the venv activated and **no production values in `.env`**: see [Demo mode (local review)](#demo-mode-local-review) in section A for Linux, macOS, PowerShell and Command Prompt. A compact Linux/macOS form is `DEMO_MODE=true SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))") python -m uvicorn main:app --host 0.0.0.0 --port 10000`, then open `http://localhost:10000/admin/login` and click **Enter Admin demo**.

### Dedicated public review demo (Vibe96 / Render)

The app contains exactly one role: **admin**. v1.0.6 can issue that role only in the isolated, explicitly enabled sandbox. Do not create public-facing credentials on a production instance.

For a **separate demo-only Render service** (recommended), deploy the complete extracted package root exactly as described in section F and set the following names in **Render → Environment**, not in a committed or uploaded `.env`:

```
SECRET_KEY=<generate-a-fresh-random-value>
DEMO_MODE=true
DEMO_SEED=review-v1
DEMO_MAX_SESSIONS=200
HTTPS_ONLY=true
DEMO_ALLOW_AI=true
AI_API_KEY=<your provider secret>
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
```

Leave `DATABASE_URL`, `ADMIN_*` and `SETUP_TOKEN` unset. **With `DEMO_MODE=true` the app refuses to start** if any of `DATABASE_URL` (other than a `sqlite:///./data/demo-<seed>/<name>.db` sandbox path), `ADMIN_USERNAME`, `ADMIN_PASSWORD` or `SETUP_TOKEN` is set, and it also refuses a blank, placeholder or short `SECRET_KEY`. `AI_API_KEY` and `AI_BASE_URL` are allowed only when `DEMO_ALLOW_AI=true`; otherwise they also prevent startup. The API key is read only from the host environment — the demo Settings page never shows it and rejects any attempt to change AI settings. Without the flag, chat stays on the scripted guided replies. For a local demo, rename any private `FrontDesk Project/.env` that contains production values first (environment variables set to an empty string in PowerShell are removed, so the `.env` value would be read). Use the landing-page root (`https://<service>.onrender.com/`) as the live-demo URL. The Live Demo button opens `/admin/login`, which includes **Enter Admin demo**. Each signed review session starts with independent fictional data. `/chat` is the visitor experience and uses the live AI when `DEMO_ALLOW_AI=true` (caps fall back to the guided replies).

If you edit an existing Render service already holding customer data, **do not turn on demo mode there**. Deploy a fresh demo service instead. For production leave `DEMO_MODE=false` and `DEMO_ALLOW_AI=false`, retain private `ADMIN_USERNAME`/`ADMIN_PASSWORD` or `SETUP_TOKEN`, and mount persistent storage for the chosen SQLite `DATABASE_URL`. Do not copy demo DB files over production.

Demo note: SQLite per-session sandboxes are intentionally disposable. They are not automatically deleted; the worker knows up to `DEMO_MAX_SESSIONS` (default 200) scopes. Single-worker deployment is mandatory for the per-worker cap; extra external disk cleanup is required for a long-running service. Render free's ephemeral filesystem may reset at restart/redeploy. Read `docs/DEMONSTRATION.md` for isolation, capacity and workflow tradeoffs.

### Private password-protected deployment (not the public one-click demo)

1. Deploy with `SECRET_KEY`, `SETUP_TOKEN` (or `ADMIN_USERNAME`/`ADMIN_PASSWORD`), and `HTTPS_ONLY=true`.
2. Optional private `ADMIN_*` bootstrap (avoid reusing real credentials):

```
ADMIN_USERNAME=demo
ADMIN_PASSWORD=<choose-a-strong-demo-password>
```

3. With `DEMO_MODE=false`, confirm `/admin/login` accepts those credentials and the dashboard loads.
4. If you choose that separate private deployment path, provide your newly chosen private review credentials only through the appropriate marketplace review-credentials field. This does not replace or weaken the recommended isolated one-click demo; never reuse personal or production credentials.
5. In **Settings**, add your own AI Base URL / API Key / Model, business name, hours.
6. Add FAQs under **Knowledge**.

Change the password later under **Admin → Settings → Change Admin Password**.

---

## D. Docker Compose (root context and root `.env`)

Compose builds the same single root Dockerfile as Render. Do not copy `requirements.lock` or any app file to the repository root. Run these steps **in this order, at the archive root**:

```bash
# 1. Linux/macOS, extracted archive root: create the private env file
cp .env.example .env
# 2. Edit .env and set (generate each value with the command below):
#      SECRET_KEY=<paste generated value>      (required, >= 32 chars)
#      SETUP_TOKEN=<paste another generated value>  (for first-run /admin/setup)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# 3. Build and start
docker compose up --build
```

```powershell
# 1. Windows PowerShell, extracted archive root
Copy-Item .env.example .env
# 2. Generate values and paste them into .env as SECRET_KEY= and SETUP_TOKEN=
py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
notepad .env
# 3. Build and start
docker compose up --build
```

If `SECRET_KEY` is missing Compose stops with `Set SECRET_KEY in .env - see .env.example`; if it is a placeholder or shorter than 32 characters the app itself refuses to start.

The app opens at `http://localhost:10000` with default settings. If root `.env` says `PORT=8080`, the host listens on 8080, mapping still goes to internal 10000. Only host-external port changes from the mapping; no source change is necessary.

- Source: root `context: .`, `dockerfile: Dockerfile`; root `.dockerignore` applies.
- Database is bind-mounted at `/app/data` ↔ `./FrontDesk Project/data`; keep actual DBs out of tracked source and image contexts.
- Use ordinary private root `.env` only for local Compose; never treat the root `.env.example` as a filled file or upload private `.env` to GitHub.
- `docker compose --env-file .env config` is a local validation/inspection command. Actual image/network startup/testing depends on available Docker, and static tests alone are not a BuildKit run.
- Manual image run (archive root): `docker build -t frontdesk-ai .` then `docker run --env-file .env -p 10000:10000 frontdesk-ai`. Public demo data only disposable details must align with `docs/DEMONSTRATION.md`.

---

## E. VPS deployment (Ubuntu 22.04 / 24.04 + nginx + HTTPS)

This section deploys FrontDesk AI on your own Linux server: a dedicated system user, a Python virtual environment, a systemd service, nginx as reverse proxy, free HTTPS with certbot, a firewall, backups and logs. Replace `frontdesk.example.com` with your domain (its DNS `A` record must point to the server's IP).

### E1. Server packages and Python 3.12

```bash
sudo apt update && sudo apt -y upgrade
sudo apt install -y nginx sqlite3 unzip ufw
# Ubuntu 24.04 ships Python 3.12:
sudo apt install -y python3.12 python3.12-venv
# Ubuntu 22.04 ships Python 3.10, so add Python 3.12 first:
#   sudo apt install -y software-properties-common
#   sudo add-apt-repository -y ppa:deadsnakes/ppa
#   sudo apt update && sudo apt install -y python3.12 python3.12-venv
python3.12 --version   # must print 3.12.x
```

### E2. Dedicated system user and app folder

```bash
sudo adduser --system --group --home /opt/frontdesk frontdesk
# Upload the ZIP (e.g. scp frontdesk-ai-v1.0.9-vibe96.zip you@server:/tmp/) then:
sudo unzip /tmp/frontdesk-ai-v1.0.9-vibe96.zip -d /opt/frontdesk/release
# A space-free symlink keeps systemd/nginx paths simple:
sudo ln -sfn "/opt/frontdesk/release/FrontDesk Project" /opt/frontdesk/app
sudo chown -R frontdesk:frontdesk /opt/frontdesk
```

Result: `/opt/frontdesk/app/main.py` exists (it is `FrontDesk Project/main.py`).

### E3. Virtual environment and dependencies

```bash
sudo -u frontdesk python3.12 -m venv /opt/frontdesk/venv
sudo -u frontdesk /opt/frontdesk/venv/bin/python -m pip install --upgrade pip
sudo -u frontdesk /opt/frontdesk/venv/bin/python -m pip install --require-hashes -r /opt/frontdesk/app/requirements.lock
```

### E4. Environment file (`.env`)

```bash
sudo -u frontdesk cp /opt/frontdesk/app/.env.example /opt/frontdesk/app/.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # run twice: SECRET_KEY, SETUP_TOKEN
sudo -u frontdesk nano /opt/frontdesk/app/.env
sudo chmod 600 /opt/frontdesk/app/.env
```

Set at least:

```ini
# 32+ characters, first generated value
SECRET_KEY=<paste>
# second generated value (or use ADMIN_USERNAME / ADMIN_PASSWORD instead)
SETUP_TOKEN=<paste>
# false while testing over plain http; true once HTTPS is active (E8)
HTTPS_ONLY=false
# production: never true on real customer data
DEMO_MODE=false
BUSINESS_NAME=Your Business
# your IANA time zone
BUSINESS_TIMEZONE=Asia/Dhaka
# blank = /opt/frontdesk/app/data/ai_receptionist.db
DATABASE_URL=
```

The app reads this `.env` from its working directory (`/opt/frontdesk/app`), so the systemd unit below does not need an `EnvironmentFile` line.

AI provider keys are entered later in **Admin → Settings** (stored encrypted), not in `.env`.

### E5. systemd service

Create `/etc/systemd/system/frontdesk.service`:

```ini
[Unit]
Description=FrontDesk AI (Uvicorn)
After=network.target

[Service]
User=frontdesk
Group=frontdesk
WorkingDirectory=/opt/frontdesk/app
ExecStart=/opt/frontdesk/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now frontdesk
sudo systemctl status frontdesk --no-pager
curl -s http://127.0.0.1:8000/health      # {"status":"ok","version":"1.0.9","demo_mode":false}
```

Keep `--workers 1`: SQLite and the in-memory rate limiter are per process. Uvicorn listens only on `127.0.0.1`; nginx is the public entry point. Tables are created (and older databases migrated) automatically at startup.

### E6. nginx reverse proxy

Create `/etc/nginx/sites-available/frontdesk`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name frontdesk.example.com;

    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        # Overwrite (do not append) so clients cannot spoof their IP for rate limits:
        proxy_set_header X-Forwarded-For   $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;            # AI replies can take several seconds
    }

    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        expires 7d;
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/frontdesk /etc/nginx/sites-enabled/frontdesk
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

FrontDesk AI uses ordinary HTTP requests only (no WebSockets), so no `Upgrade`/`Connection` headers are needed. The forwarded headers let Uvicorn (`--proxy-headers --forwarded-allow-ips=127.0.0.1`) see the real visitor IP and `https` scheme.

### E7. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'      # ports 80 and 443
sudo ufw enable
sudo ufw status
```

Port 8000 stays closed to the internet.

### E8. HTTPS with certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d frontdesk.example.com --redirect -m you@example.com --agree-tos
sudo certbot renew --dry-run      # auto-renewal check (a systemd timer is installed)
```

Then set `HTTPS_ONLY=true` in `/opt/frontdesk/app/.env` and run `sudo systemctl restart frontdesk`. Session cookies are now sent over HTTPS only.

### E9. First admin

Open `https://frontdesk.example.com/admin/setup`, enter a username, a strong password and your `SETUP_TOKEN` (or log in at `/admin/login` if you used `ADMIN_USERNAME`/`ADMIN_PASSWORD`). Then fill **Admin → Settings** (business name, hours, AI provider) and **Admin → Knowledge**.

### E10. Updating to a new version

```bash
sudo systemctl stop frontdesk
sudo cp -a /opt/frontdesk/app/.env /opt/frontdesk/env.backup
sudo -u frontdesk sqlite3 /opt/frontdesk/app/data/ai_receptionist.db ".backup '/opt/frontdesk/pre-update.db'"
sudo unzip -o /tmp/frontdesk-ai-vNEW-vibe96.zip -d /opt/frontdesk/release-new
sudo cp -a /opt/frontdesk/app/.env "/opt/frontdesk/release-new/FrontDesk Project/.env"
sudo cp -a /opt/frontdesk/app/data/. "/opt/frontdesk/release-new/FrontDesk Project/data/"
sudo ln -sfn "/opt/frontdesk/release-new/FrontDesk Project" /opt/frontdesk/app
sudo chown -R frontdesk:frontdesk /opt/frontdesk
sudo -u frontdesk /opt/frontdesk/venv/bin/python -m pip install --require-hashes -r /opt/frontdesk/app/requirements.lock
sudo systemctl start frontdesk && curl -s http://127.0.0.1:8000/health
```

Keep the same `SECRET_KEY` (it also decrypts the stored AI key). To roll back, point the symlink back to the old release folder and restore `pre-update.db`.

### E11. Backups

```bash
# Daily consistent SQLite backup at 02:30, keep 14 days:
sudo mkdir -p /opt/frontdesk/backups && sudo chown frontdesk:frontdesk /opt/frontdesk/backups
sudo -u frontdesk crontab -e
# add this line:
30 2 * * * sqlite3 /opt/frontdesk/app/data/ai_receptionist.db ".backup '/opt/frontdesk/backups/frontdesk-$(date +\%F).db'" && find /opt/frontdesk/backups -name 'frontdesk-*.db' -mtime +14 -delete
```

Also keep a private copy of `.env` (without it the stored AI key cannot be decrypted). Copy backups off the server regularly. Restore: stop the service, copy a backup over `data/ai_receptionist.db`, start the service.

### E12. Logs and troubleshooting

```bash
sudo journalctl -u frontdesk -f                 # application logs (live)
sudo journalctl -u frontdesk --since "1 hour ago"
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
sudo systemctl restart frontdesk                # after .env changes
```

- **502 Bad Gateway:** the service is not running; check `journalctl -u frontdesk`. A blank or short `SECRET_KEY` stops startup on purpose.
- **Login loops back to the login page over http:** `HTTPS_ONLY=true` requires HTTPS; finish E8 or set it to `false` while testing.
- **Permission denied on `data/`:** `sudo chown -R frontdesk:frontdesk /opt/frontdesk`.

---

## F. GitHub → Render hosting

Follow **`GITHUB-RENDER.md`** for complete instructions, exact repository root shape, conflict cleanup by you, notes on the previously copied root lockfile, and how correct Docker COPY sources avoid `uvicorn main:app` import failure.

| Render setting | Exact value |
|---|---|
| Runtime / Language | **Docker** |
| Root Directory | **blank** (repository root) |
| Dockerfile Path | **./Dockerfile** |
| Build / Docker Context | **.** (repository root) |
| Docker Command | **blank** — root Dockerfile CMD |
| Build Command | **blank / not applicable** for Docker |
| Start Command override | **blank / not applicable** |
| Health Check Path | **/health** |
| Instances | **1** while SQLite is used / for demo cap |

The canonical root `render.yaml` sets rootDir `.`, Dockerfile path `./Dockerfile`, context `.`, Docker runtime, single worker and liveness check. It omits native build/start overrides. Repository application stays nested; inside the image `/app/main.py` is valid. Production defaults are explicit `DEMO_MODE=false`, `HTTPS_ONLY=true`.

`SECRET_KEY generateValue: true` supported by Render Blueprint generates a random base64-encoded 256-bit value **when a variable does not already exist**. Later Blueprint syncs preserve existing secrets. `sync: false` variables prompt at first creation, but new entries on later syncs are ignored; manual Docker service configuration requires input through Render Environment instead. Generate a new fresh secret manually outside Blueprint if needed. Nothing secret is committed with this package.

To provision one-click admin review correctly use a **separate, dedicated, clean review service** with:

```text
SECRET_KEY        = freshly generated by Render or manually generated securely
DEMO_MODE         = true
DEMO_SEED         = review-v1
DEMO_MAX_SESSIONS = 200
HTTPS_ONLY        = true
DEMO_ALLOW_AI     = true
AI_API_KEY        = <your provider secret>
AI_BASE_URL       = https://api.openai.com/v1
AI_MODEL          = gpt-4o-mini
```

Leave `ADMIN_*`, `SETUP_TOKEN` and `DATABASE_URL` blank/unset. A demo service that still has a production `DATABASE_URL`, admin or setup credential **fails at startup**. Without `DEMO_ALLOW_AI=true`, a set `AI_API_KEY` or `AI_BASE_URL` also fails startup. Keep customer data off this service. Use **1 instance**; the Dockerfile start command is `uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}` (Python 3.12.7, single worker). Root Directory stays **blank** (repository root, not `FrontDesk Project`).

Render can preserve data with a paid persistent disk mounted at `/app/data`, or use an owner-managed persistent DB when configured. This archive does not create disk, credential or database resources. Sandbox SQLite/session files are not automatically deleted; per-worker cap max/default 200 assigned seed `review-v1`. `numInstances=1` avoids implying distributed scope quota. Free demo filesystem resets are expected; other periods require owner external cleanup scheduling.

Before using root `https://<your-service>.onrender.com/` as your separate review URL, verify your own real deployment and app pages. This guide never claims an action outside local source modifications.

---

## G. Branding (name, logo, colours)

Branding needs no code changes to the Python files; restart the app after editing templates or CSS (`sudo systemctl restart frontdesk`, or stop/start `uvicorn` locally). Hard-refresh the browser (Ctrl+F5) to see CSS changes.

1. **Business name (shown to visitors and in the admin header):** Admin → Settings → *Business name*, or `BUSINESS_NAME` in `.env` for the default before the first save.
2. **Product name in page titles and the sidebar:** the text `FrontDesk AI` appears in `FrontDesk Project/templates/*.html` (mainly `base.html`, `landing.html`, `login.html`, `chat.html`, `setup.html`). Search and replace it with your brand, e.g. in VS Code "Replace in Files" limited to the `templates` folder.
3. **Logo (no code needed):** sign in and open **Admin → Settings → Brand logo**. Choose a PNG, JPG or WEBP file (max 1 MB, max 2000 × 2000 px; a square logo on a transparent or white background works best) and click **Upload logo**. It replaces the default "F" mark everywhere: admin sidebar, login and setup pages, landing page header and footer, visitor chat (top bar, chat header and the small avatar next to every receptionist reply) and the browser-tab icon. **Remove logo / use default** brings the "F" back.
   - SVG files are refused (they can contain scripts); the real file content is checked, not just the file name.
   - Files are stored outside the templates in `uploads/<business id>/` next to the SQLite database (`FrontDesk Project/data/uploads/` by default, `/app/data/uploads/` in Docker, so the existing `frontdesk-data` volume keeps them) under a random name, and served from `/brand/logo/<business id>`. Include this folder in your backups (section E11). It is ignored by git and Docker builds.
   - Logo upload is disabled in the public demo (`DEMO_MODE=true`); the demo always shows the "F" mark.
   - To change the default letter instead, edit `<span class="logo-mark ...">F</span>` in `FrontDesk Project/templates/_brand.html`.
4. **Browser tab icon:** replace `FrontDesk Project/static/favicon.svg` (keep the file name, or update the `<link rel="icon">` lines in `base.html` and `landing.html`).
5. **Chat assistant avatar:** replace `FrontDesk Project/static/avatar.jpg` with a square image of the same name.
6. **Colours:** the primary brand colour is `#5064eb` (hover `#4353d7`); the logo/nav gradient uses `#6376f3`, `#7d67de` and `#596cec`. Replace these hex values in `FrontDesk Project/static/app.css`, and in the few inline `[#5064eb]` Tailwind classes in `admin.html`, `base.html`, `landing.html` and `login.html`. Example: `sed -i 's/#5064eb/#0f9d76/g' static/app.css templates/*.html`.
7. **Landing page text and screenshots:** edit `templates/landing.html`; its images live in `static/` (`admin-demo-dashboard.png`, `04-chat-greeting.jpg`).
8. **Hours, appointment length, holidays and FAQs:** Admin → Settings (`opening_hour`, `closing_hour`, **Appointment length (minutes)**, `closed_days`, `holiday_dates`) and Admin → Knowledge.


---

## H. Booking rules (buyers)

- Hours and closed weekdays are configurable (defaults: Mon–Sat 09:00–18:00, closed Sunday).
- Holiday dates (`YYYY-MM-DD` list) are rejected by the booking tool.
- **Appointment length:** Admin → Settings → Business profile → **Appointment length (minutes)**. Whole minutes from 5 to 480 in steps of 5 (default 60). It is used for:
  - the end time of new bookings and the confirmation text (e.g. "10:00 AM – 10:30 AM (30 minutes)");
  - the chat welcome message, the note under the message box, the "Appointment length" quick question and the AI instructions;
  - the closing-time check: an appointment must **end** by the closing hour (with 30 minutes and closing at 18:00, the latest start is 17:30);
  - the landing page "min" figure and the "New booking length" figure on Appointments.
- Existing appointments keep the length they were booked with (stored per appointment), so changing the setting never moves or shortens old bookings. Databases from earlier versions are upgraded automatically (length 60).
- Overlapping appointments are rejected; each existing appointment is checked with its own length.
- Duplicate phone: one confirmed appointment per phone number.
- Dates: weekday is computed from the real calendar date in `BUSINESS_TIMEZONE`. Accepted: `10th November at 5pm`, `November 10 2pm`, `2026-11-10 17:00`, `day after tomorrow at 5pm`, `next Monday 10am`. Ambiguous (`10/11`), missing date/time, past or conflicting weekday inputs get a clarification question instead of a guess.

## J. Example AI providers

| Provider | AI Base URL | Example Model |
|----------|-----------------------------|-------------------------|
| Groq | https://api.groq.com/openai/v1 | `openai/gpt-oss-20b` |
| OpenAI | https://api.openai.com/v1 | `gpt-4o-mini` |
| OpenRouter | https://openrouter.ai/api/v1 | `google/gemini-flash-1.5` |
| Together AI | https://api.together.xyz/v1 | Various open models |
| Local (Ollama) | http://localhost:11434/v1 | `llama3.2` |

## K. Production notes

- Generate and set `SECRET_KEY` before going live. The app **refuses to start** with the placeholder.
- Set `SETUP_TOKEN` (or use `ADMIN_PASSWORD` bootstrap) before exposing the site.
- Use a reverse proxy and HTTPS; set `HTTPS_ONLY=true`.
- Do not commit or share your real `.env`, API keys, or `*.db` files.
- Admin auth uses a signed session cookie (`frontdesk_session`) with `role=admin`. A plain `admin=true` cookie is rejected.
- AI API keys are encrypted at rest (Fernet derived from `SECRET_KEY`).
- See [docs/SECURITY.md](docs/SECURITY.md) for the full route/guard table.


## L1. Upgrade v1.0.8 → v1.0.9 (existing installation)

1. Back up `.env` and `data/` (see E11). Keep the same `SECRET_KEY`.
2. Replace the files with the v1.0.9 package (VPS: section E10; Render: upload the new root contents to GitHub).
3. Reinstall dependencies: `python -m pip install --require-hashes -r requirements.lock` (the lock was regenerated; one minor transitive update).
4. Start the app. On startup it adds the new `businesses` table and a `business_id` owner column to appointments, conversations and knowledge items, and assigns every existing row to your business (id 1). No manual SQL is needed and no data is removed.
5. Admins are asked to sign in once more, because v1.0.9 sessions also carry the owning business.

## L0. Upgrade v1.0.5 → v1.0.6 (existing service)

1. Back up production `.env` and `data/` first. Upload all extracted v1.0.6 root contents to the repository root and **delete** `FrontDesk Project/Dockerfile`, `FrontDesk Project/.dockerignore`, `FrontDesk Project/.gitignore` and `FrontDesk Project/routes/admin.py` from GitHub (replaced by the root Dockerfile/ignore files and the `routes/admin/` package).
2. Render settings are unchanged (Root Directory blank, `./Dockerfile`, context `.`, Docker Command blank, `/health`).
3. Production: make sure `SECRET_KEY` is at least 32 characters (Render `generateValue` already is).
4. Demo service: remove `DATABASE_URL`, `ADMIN_*` and `SETUP_TOKEN` from its Environment, otherwise it will refuse to start. To keep live AI replies set `DEMO_ALLOW_AI=true` and provide `AI_API_KEY` (plus `AI_BASE_URL` / `AI_MODEL`); without that flag a set AI key still prevents startup.
5. Dependencies were re-locked (patch/minor updates); reinstall with `pip install --require-hashes -r requirements.lock` for local runs.

## L. Upgrade v1.0.4 → v1.0.5 (existing service)

1. Back up your production `.env`, configured database and SQLite `data/` files before replacing anything. Test restore separately. This ZIP intentionally contains no live database or private environment.
2. On GitHub upload **all extracted v1.0.5 root contents** to repository root. Replace this release's root `Dockerfile`, `render.yaml`, Compose file and ignore files as needed; remove obsolete manually duplicated root `requirements.lock` and conflicting stale deployment files after reviewing them. Keep production runtime data private and outside that upload.
3. For a manual Render service use Runtime Docker, Root Directory blank, Dockerfile Path `./Dockerfile`, Build Context `.`, Docker Command blank and Health Path `/health`. Do not switch back to the nested Python service or copy the old Dockerfile to the root.
4. For local/VPS upgrades always run from `FrontDesk Project/`, retain its private `.env`, install from the unchanged `requirements.lock`, preserve `SECRET_KEY` for existing sessions and keep `DEMO_MODE=false` for production. Do not overwrite live data files with examples.
5. Test imports, `/health`, login, admin forms, booking and storage on staging before changing a public deployment. Dependencies and runtime functionality have no intended behavior change beyond version identification. Root Docker copies the same nested source into `/app`; it does not require root `main.py`.
6. For a public reviewer use a separate clean service with the opt-in demo values from section C/F. Do not reconfigure production as demo. SQLite requires one process/worker here; enable persistent storage or an owner-managed database for production, and external cleanup for long-running demos.

## M. Render troubleshooting

- **`No module named main` / `uvicorn main:app` failure:** confirm you uploaded every ZIP-root item, not the ZIP or an extra outer directory. Delete only the obsolete manually duplicated root lockfile after review; do not copy the nested app to root. Use `./Dockerfile` and context `.` so `/app/main.py` is built from `FrontDesk Project/main.py`.

- **Root is chat or 404:** verify the v1.0.5 `FrontDesk Project` content and verify `routes/public.py` contains both landing `/` and chat `/chat`. Clear any platform cache only through standard deployment mechanisms.
- **No one-click demo button:** explicitly set `DEMO_MODE=true` on the *dedicated clean review* service and restart. This behaviour is intentionally absent in production.
- **Login redirects to setup:** production DB has no admin hash. Configure `SETUP_TOKEN` or use private `ADMIN_*`; this does not apply to demo mode.
- **App seeded but another reviewer's chat is missing:** intended isolation. Each signed review session has an independent fictional store.
- **AI replies are deterministic:** intended in demo mode to avoid costs and secret exposure. Production uses your own provider settings with the API key encrypted at rest.
- **Dedicated demo on nested-only service:** do not use a nested-only GitHub repository with this root-first package. Deploy full package root so the root Dockerfile correctly produces `/app/main.py`; opt into demo only in the separate clean environment described in section F.
- **Client IP / proxy handling:** the image CMD runs `uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}`. Its `${PORT}` is expanded by the Linux shell, matching Render-supplied ports. The app reads `request.client.host` for rate limiting. If operating behind a trusted reverse proxy, configure Uvicorn forwarded behavior only at the proxy boundary you trust; the VPS example allows only `127.0.0.1`. Consult Render’s current documentation before changing their trusted-proxy defaults. Do not blindly trust forwarded headers from arbitrary clients.
- **Free filesystem disappears:** demo data is disposable. Use persistent storage for production; do not rely on Render free SQLite persistence.
- **Both examples drifted:** copy either `.env.example` over the other and run the comparison commands in the initial layout section. Never merge a filled `.env` into an example.
- **Local `.env` is not found / placeholder SECRET_KEY is rejected:** run `pwd` / `Get-Location` first. From `FrontDesk Project`, confirm `Test-Path main.py`, `Test-Path .env`, then restart. The dotenv path is resolved against the invocation working directory, not the ZIP-root Compose `.env`. Activating venv does not itself change directory.
- **Render needs secrets:** fill Render Environment settings rather than committing/uploading `.env`. The dedicated demo discards configured production DSN/admin/bootstrap/AI values before engine creation but still requires a fresh secret and clean isolated deployment.
- **Archive contains old screenshots:** `docs/screenshots/` are intentionally marked as v1.0.3 product examples for documentation. The landing page uses the actual new admin demo-dashboard screenshot plus a retained visitor-workflow example. The outdated pricing/duration showcase has been removed.
