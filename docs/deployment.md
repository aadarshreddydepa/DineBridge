# Deployment plan

Assumption: “Resin” means **Render**. This document describes a development or demonstration deployment. A live restaurant ordering service needs persistent database backups, a responsive API during service hours, and reliable event delivery.

## What runs where

| Component | Local development | Free demonstration | Live restaurant use |
| --- | --- | --- | --- |
| PostgreSQL | Compose `db` service | External PostgreSQL provider such as Neon Free | Managed PostgreSQL with backups and tested restores |
| Django API | Compose `api` service | Render Free web service using this repository's Dockerfile | Always-on service, monitoring, deployment rollback |
| React customer menu | Vite on `127.0.0.1:5173` | Vercel Hobby for personal/noncommercial demonstration | A plan that permits commercial use, or another suitable static host |
| Menu/brand images | Local development storage | External object storage | Durable object storage and CDN |
| Event worker | Future local process/container | No durable free Render worker assumed | Dedicated worker or equivalent reliable process |

The local Compose database is **not** the production database. Render builds the Django application image from `Dockerfile`; its managed database or an external provider supplies `DATABASE_URL`. Vercel builds the React app in `frontend/`. Its small same-origin function forwards `/api/v1/*` and `/q/*` to Render using server-side `API_ORIGIN`. Database credentials and Django secrets stay on Render, never in Vercel frontend variables.

## Deployment sequence

1. Create a PostgreSQL database in a managed provider. Set its region as close to Render as practical. Save its SSL-required connection URL as Render's `DATABASE_URL`.
2. Apply the SQL migrations from a trusted machine using `DATABASE_URL='...' .venv/bin/python db/migrate.py`. Render Free does not provide a pre-deploy command or shell; use a paid pre-deploy step later. Do not put `DATABASE_URL` in version control.
3. Deploy this repository's Dockerfile as a Render web service. Configure `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` for the Render hostname, `CSRF_TRUSTED_ORIGINS` for the Vercel frontend origin, `FRONTEND_URL` and `QR_PUBLIC_BASE_URL` both set to the Vercel frontend origin, and `ASSET_BASE_URL`. The image binds to Render's `PORT` on `0.0.0.0`.
4. Deploy the `frontend/` directory to Vercel with Vite build command `npm run build` and output directory `dist`. Set server-side `API_ORIGIN` to the Render API origin, such as `https://example.onrender.com`. Leave `VITE_API_BASE_URL` unset. The frontend calls its own `/api/v1/*`, and table QR links point to its own `/q/*`; `frontend/api/proxy.ts` forwards them to Render so access and CSRF cookies belong to the Vercel site. Keep `COOKIE_SAMESITE=Lax` and HTTPS in production.
5. Store logos and menu photos in durable object storage. Do not rely on Render's local filesystem.
6. Before a real restaurant pilot, add backups, restore tests, monitoring, and a durable event worker. Exercise the full scan-to-order-to-billing flow during a Render cold start and database interruption.

## Free-tier limits affecting this product

- Render's Free web service spins down after 15 minutes without inbound traffic and can take about a minute to wake. Its local filesystem is ephemeral. This is unsuitable for a kitchen screen that must receive timely orders.
- Render Free PostgreSQL expires after 30 days and has no backups. Use it only for a disposable demonstration, not restaurant order history.
- Vercel Hobby is limited to personal, noncommercial use. A deployed client restaurant portal requires a plan or host whose terms permit commercial use.
- Vercel does not provide its former first-party Postgres product; its Postgres integrations use external providers. The Django API, not the Vercel frontend, should connect to the database.
- A free API instance and free database may both sleep or restart. The production design needs authoritative order snapshots and a durable outbox; SSE is only a delivery channel.

Useful provider references: [Render Free limitations](https://render.com/docs/free), [Render Docker deployment](https://render.com/docs/docker), [Vercel Hobby terms](https://vercel.com/docs/plans/hobby), [Vercel Postgres](https://vercel.com/docs/postgres), [PostgreSQL 18 container data path](https://hub.docker.com/_/postgres).
