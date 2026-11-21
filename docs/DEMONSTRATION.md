# Isolated public demonstration

## Why an explicit instance is necessary

The public Admin Demo button intentionally grants the application's single real admin role. It must not be a bypass on a production account. Enable `DEMO_MODE=true` only on a dedicated review service with no real production credentials or customer data and a fresh `SECRET_KEY`. A production deployment should keep the setting false, preserve `DATABASE_URL`, and use private `ADMIN_USERNAME`/`ADMIN_PASSWORD` or token-protected setup.

## Isolation mechanics

- At import, demo mode substitutes a local engine path below `data/demo-<seed>/` **before any engine is created**. Production's configured `DATABASE_URL` is not opened by the app.
- Admin login is a `POST /admin/demo-login` action requiring a session CSRF token and ordinary login rate limiting. No role is accepted from the browser; the server chooses the sole admin role.
- A random scope is put in the signed session and mapped to an opaque SQLite filename (a scoped hash, never user-supplied as a path). Separate production/demo cookie names and keys prevent replay across mode changes.
- Public demo chat creates a scope in that visitor's signed cookie before chat processing. After an admin demo login, visitor chat demo data with another scope is not trusted for deleting listed records.
- The seeded fictional business is a *sample* with nonsensical reserved 555 telephone numbers, never real vendor contact/secret data.
- Regenerating the dataset is safe and idempotent: seed only when that isolated database has no knowledge items. If a reviewer wipes the whole DB externally it is recreated on next use. Normal deleting/adding/editing never resets the user's whole session.

## What a public reviewer can/cannot change

| Operation | Demo | Production |
|---|---|---|
| View seeded KPIs, appointments, conversations, settings | Yes | Private admin only |
| Change status of an appointment booked in the chat during this session | Yes | Private admin + CSRF + `demo_blocks_mutation` |
| Change status of seeded appointments | No | Read-only fixtures (403) |
| Add/edit/delete own FAQ records | Own scope plus server CSRF/ownership | Private admin + CSRF |
| Delete own admin-demo-created conversation | Own scope plus server CSRF/ownership | Private admin + CSRF |
| Delete/override seeded FAQ or other reviewer's FAQ/chat | **403** | Private admin only |
| Chat / book | Scripted guided replies, or live host AI when `DEMO_ALLOW_AI=true` (bookings still go only to the sandbox) | Normal public endpoint with core ownership checks |
| Configure API providers / change business hours | **403** | Private admin + CSRF |
| Ordinary credential login, account change, setup | **Blocked** | Authentication + existing protections |

By default, demo chat is a deterministic guided workflow: it never constructs an AI `httpx` client and returns local responses. It processes the exact local booking parser already used by the production tool, so overlap/hours validations still apply.

When the operator sets `DEMO_ALLOW_AI=true` and provides `AI_API_KEY` (optionally `AI_BASE_URL` / `AI_MODEL`) on that dedicated demo service, visitor `/chat` uses the host provider. The key comes only from the environment; it is never shown in HTML, JavaScript, Settings, logs or error messages, and reviewers cannot change it. Live AI is capped per session (`DEMO_AI_MAX_MESSAGES`, default 30), per UTC day (`DEMO_AI_DAILY_LIMIT`, default 500), per IP and per session rate, input length and `max_tokens`. When a cap is reached, chat falls back to the guided replies with a short note. Bookings still write only to the per-session sandbox.

## Capacity and operations limits

- Default cap: 200 **known in-worker** scopes (`DEMO_MAX_SESSIONS`, clamped 1–1000). Requests creating above the cap receive a demo-busy status/login redirect. Existing sessions remain usable.
- Use one uvicorn worker for the public demo under SQLite. The cap is not a distributed quota.
- Files in `data/demo-<seed>/` and DB records are not automatically purged. Put cleanup in operational maintenance/reset, and constrain disk usage at the platform; in-process quota alone is not an unbounded storage guarantee. This package intentionally includes no external scheduler.
- Render's free ephemeral disk can clear a sandbox during restart/redeploy. Log a demo admin back in to start a clean sample. Production needs persistent storage; demo filesystem loss is irrelevant to production data.
