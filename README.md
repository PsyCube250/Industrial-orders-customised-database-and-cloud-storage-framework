# ProdFlow (backend)

Manufacturing order & production management API, built from the spec in
`新建 Microsoft Excel 工作表.xlsx`. Covers 8 modules: Order Management, Sample
Management, Procurement/Materials, Material Prep, Production Management,
Packaging, Messaging & Timeout Reminders, and System Admin.

Stack: **FastAPI + SQLAlchemy**, **PostgreSQL** (via Docker) or SQLite (local
dev). This repository is backend-only — the frontend is developed and deployed
separately and talks to this API over `/api/*` (plus `/uploads/*` for
authenticated file serving).

Order Management is fully implemented end-to-end (entry, bulk Excel import,
search, tracking with progress steps and overdue flags, delivery
date/pause/cancel/resume changes, and a statistics endpoint). The other 7
modules have full data models and working CRUD APIs, wired to the same auth
and database, but without the deeper business logic (auto shortage detection,
WeChat push, escalation cron) called out in the spec — those are marked as
follow-up work.

## Quick start — Docker (recommended, uses Postgres)

```bash
docker compose up --build
```

Caddy fronts the API on ports 80/443 — `db` and `backend` are not published
to the host directly, only reachable inside the Docker network.

- API root: https://217.154.42.76.sslip.io/api (interactive docs at `/docs`)
- Login: `POST /api/auth/login` with `admin` / `admin123` (seeded automatically
  on backend startup)

## Production deployment (Linux server, HTTPS)

Let's Encrypt (and therefore Caddy's automatic HTTPS) cannot issue a
certificate for a bare IP address, only for a hostname. Since this server
doesn't have a real domain pointed at it yet, we use
**[sslip.io](https://sslip.io)** — a free wildcard DNS service where any
hostname of the form `<ip-with-dots>.sslip.io` resolves to that IP with zero
DNS setup. `Caddyfile` is already configured for `217.154.42.76.sslip.io`.

Steps on the server:

1. Open ports 80 and 443 in the firewall/security group (needed for Let's
   Encrypt's HTTP-01 challenge and for HTTPS traffic itself).
2. `docker compose up --build -d`
3. Caddy automatically requests and renews a trusted cert on first request.

If you later get a real domain, just replace the hostname at the top of
`Caddyfile` and restart the `caddy` service — no other changes needed.

Also change `SECRET_KEY` and the Postgres password in `docker-compose.yml`
before exposing this beyond your own testing — both are placeholder dev
values right now.

## Quick start — local dev (SQLite, no Docker)

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.seed        # creates prodflow.db + admin user (admin/admin123)
uvicorn app.main:app --reload --port 8000
```

API at http://localhost:8000/api, interactive docs at
http://localhost:8000/docs.

To point the local backend at Postgres instead of SQLite, copy
`backend/.env.example` to `backend/.env` and set `DATABASE_URL`.

CORS is configured for a frontend dev server at `http://localhost:5173`
(`backend/app/main.py`); add your frontend's origin there if it runs
elsewhere. In production, serving the frontend behind the same Caddy host
makes requests same-origin, so no CORS change is needed.

## Project layout

```
backend/app/
  models/       SQLAlchemy models, one file per module
  schemas/      Pydantic request/response schemas (orders + auth)
  routers/      FastAPI routers, one per module
  auth.py       JWT auth, password hashing
  deps.py       Shared request validation helpers
  main.py       App wiring, CORS, authenticated /uploads serving
  seed.py       Seeds admin user + base data
```

## Notes

- User roles: `admin`, `supervisor`, `director`, `staff`. Some endpoints
  (creating users, notification rules) require `admin`/`supervisor`.
- File uploads (order attachments, sample photos) are stored under
  `backend/uploads/` locally, or the `uploads_data` Docker volume, and served
  only to authenticated users via `GET /uploads/{path}` (bearer header or
  `?token=` query parameter).
