# SmartTransitSystem

A modular transit platform for matatu/bus operators in Kenya — real-time seat booking, live vehicle tracking, and fleet operations, built as a foundation that scales toward microservices as the platform grows.

## Vision

Commuters know exactly when their bus is coming and have a confirmed seat before they board. Operators know exactly who is on each vehicle and what they paid. Everything else — parcel delivery, on-road flagging, fleet analytics, marketing — builds on top of that core loop.

## Architecture

Built as a modular monolith by design: one Django backend, one React frontend, one PostgreSQL+PostGIS database, and Redis — structured so each domain (booking, tracking, notifications) can be split into its own service later without a rewrite.

Backend:    Django + DRF + Django Channels

Database:   PostgreSQL 15 + PostGIS

Cache:      Redis 7

Queue:      Celery + Redis

Frontend:   React + Vite + Tailwind (coming in a later phase)

Maps:       Mapbox GL JS

Payments:   M-Pesa Daraja API

SMS:        Africa's Talking


## Project Status

**Phase 0 — Foundation & DevOps: complete**
- Docker Compose orchestration for backend, PostgreSQL+PostGIS, Redis, and a Celery worker
- Django project initialized with GeoDjango (`django.contrib.gis`) support
- Environment-based configuration via `python-decouple`
- JWT auth, CORS, and Django Channels wired into settings (not yet used by any endpoints)
- Celery bootstrapped and confirmed connected to Redis

**Phase 1 — Data Models & Multi-Tenancy: in progress**

See the project plan for the full phase breakdown (routes/trips, booking flow, real-time tracking, conductor tools, fleet dashboard, and beyond).

## Local Development

### Prerequisites
- Docker Engine + Docker Compose plugin

### Setup

1. Clone the repo
2. Create `backend/.env` (not committed — see `.gitignore`) with the required variables: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DB_HOST`, `DB_PORT`, `REDIS_HOST`, `REDIS_PORT`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
3. Build and start all services:

\`\`\`bash
docker compose up --build
\`\`\`

4. In a separate terminal, apply migrations:

\`\`\`bash
docker compose exec backend python manage.py migrate
\`\`\`

The API will be available at `http://localhost:8000`.

## Deployed Production Links

The platform is deployed and accessible live at the following production URLs:

- **Commuter Application (User Portal)**: [smarttransitsystem-frontend.onrender.com](https://smarttransitsystem-frontend.onrender.com)
  - *No passwords required — automatic passwordless device handshake.*
- **Fleet Owner & Staff Dashboard**: [smarttransitsystem-admin.onrender.com](https://smarttransitsystem-admin.onrender.com)
  - *Login form portal for fleet owners, conductors, and drivers.*
- **Backend API Server**: [smarttransistsystem.onrender.com](https://smarttransistsystem.onrender.com)

## License

Not yet decided.